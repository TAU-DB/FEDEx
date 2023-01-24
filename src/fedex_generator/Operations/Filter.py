import operator
import pandas as pd

from fedex_generator.commons.consts import TOP_K_DEFAULT, DEFAULT_FIGS_IN_ROW
from fedex_generator.commons import utils
from fedex_generator.commons.DatasetRelation import DatasetRelation
from fedex_generator.Operations import Operation
from fedex_generator.Measures.ExceptionalityMeasure import ExceptionalityMeasure

operators = {
    "==": operator.eq,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "!=": operator.ne,
    "between": lambda x, tup: x.apply(lambda item: tup[0] <= item < tup[1])
}


def do_operation(a, b, op_str):
    return operators[op_str](a, b)


class Filter(Operation.Operation):
    def __init__(self, source_df, source_scheme, attribute=None, operation_str=None, value=None, result_df=None):
        super().__init__(source_scheme)
        self.source_df = source_df.reset_index()
        self.attribute = attribute
        self.source_scheme = source_scheme

        if result_df is None:
            self.operation_str = operation_str
            self.value = value
            self.result_df = self.source_df[do_operation(self.source_df[attribute], value, operation_str)]
        else:
            self.result_df = result_df
        self.source_name = utils.get_calling_params_name(source_df)

    def get_correlated_attributes(self):
        numeric_df = self.source_df.head(10000)  # for performance we take part of the DB
        for column in numeric_df:
            try:
                if utils.is_numeric(numeric_df[column]):
                    continue

                items = sorted(numeric_df[column].dropna().unique())
                items_map = dict(zip(items, range(len(items))))
                numeric_df[column] = numeric_df[column].map(items_map)
            except Exception as e:
                print(e)

        # for performance, we use the first 50000 rows
        # first_rows = self.source_df.head(50000)
        # corr = first_rows.corr('spearman')
        corr = numeric_df.corr()
        high_correlated_columns = []
        if self.attribute in corr:
            df = corr[self.attribute]

            df = df[df > 0.85].dropna()
            high_correlated_columns = list(df.index)

        return high_correlated_columns

    def iterate_attributes(self):
        high_correlated_columns = self.get_correlated_attributes()

        for attr in self.result_df.columns:
            if attr.lower() == "index" or attr.lower() == self.attribute.lower() or \
                    self.source_scheme.get(attr, None) == 'i' or attr in high_correlated_columns:
                continue
            yield attr, DatasetRelation(self.source_df, self.result_df, self.source_name)

    def get_source_col(self, filter_attr, filter_values, bins):
        if filter_attr not in self.source_df:
            return None

        binned_col = pd.cut(self.source_df[filter_attr], bins=bins, labels=False, include_lowest=True,
                            duplicates='drop')

        return binned_col[binned_col.isin(filter_values)]

    def explain(self, schema=None, attributes=None, top_k=TOP_K_DEFAULT,
                figs_in_row: int = DEFAULT_FIGS_IN_ROW, show_scores: bool = False, title: str = None):
        """
        Explain for filter operation

        :param schema: dictionary with new columns names, in case {'col_name': 'i'} will be ignored in the explanation
        :param attributes: only this attributes will be included in the explanation calculation
        :param top_k: top k explanations number, default one explanation only.
        :param show_scores: show scores on explanation
        :param figs_in_row: number of explanations figs in one row
        :param title: explanation title

        :return: explain figures
        """

        if attributes is None:
            attributes = []

        if schema is None:
            schema = {}

        measure = ExceptionalityMeasure()
        scores = measure.calc_measure(self, schema, attributes)
        figures = measure.calc_influence(utils.max_key(scores), top_k=top_k, figs_in_row=figs_in_row,
                                         show_scores=show_scores, title=title)
        return figures

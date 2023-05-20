import pandas as pd

from fedex_generator.commons.consts import TOP_K_DEFAULT, DEFAULT_FIGS_IN_ROW
from fedex_generator.commons import utils
from fedex_generator.commons.DatasetRelation import DatasetRelation
from fedex_generator.Operations import Operation
from fedex_generator.Measures.NormalizedDiversityMeasure import NormalizedDiversityMeasure
from fedex_generator.Measures.DiversityMeasure import DiversityMeasure


class GroupBy(Operation.Operation):
    def __init__(self, source_df, source_scheme, group_attributes, agg_dict, result_df=None, source_name=None):
        super().__init__(source_scheme)
        self.source_scheme = source_scheme
        self.group_attributes = group_attributes
        self.agg_dict = agg_dict
        self.source_name = source_name
        if result_df is None:
            self.source_name = utils.get_calling_params_name(source_df)
            source_df = source_df.reset_index()
            group_attributes = self.get_one_to_many_attributes(source_df, group_attributes)
            self.result_df = source_df.groupby(group_attributes).agg(agg_dict)
        else:
            self.result_df = result_df
        self.result_df.columns = self._get_columns_names()

    def iterate_attributes(self):
        for attr in self.result_df.columns:
            if attr.lower() == "index":
                continue
            yield attr, DatasetRelation(None, self.result_df, self.source_name)

    def get_source_col(self, filter_attr, filter_values, bins):
        return None

    def explain(self, schema=None, attributes=None, top_k=TOP_K_DEFAULT,
                figs_in_row: int = DEFAULT_FIGS_IN_ROW, show_scores: bool = False, title: str = None, corr_TH: float = 0.7):
        """
        Explain for group by operation
        :param schema: dictionary with new columns names, in case {'col_name': 'i'} will be ignored in the explanation
        :param attributes: only this attributes will be included in the explanation calculation
        :param top_k: top k explanations number, default one explanation only.
        :param show_scores: show scores on explanation
        :param figs_in_row: number of explanations figs in one row
        :param title: explanation title

        :return: explain figures
        """
        if schema is None:
            schema = {}

        if attributes is None:
            attributes = []
        measure = DiversityMeasure()
        # measure = NormalizedDiversityMeasure()
        scores = measure.calc_measure(self, schema, attributes)
        figures = measure.calc_influence(utils.max_key(scores), top_k=top_k, figs_in_row=figs_in_row,
                                         show_scores=show_scores, title=title)
        return figures

    @staticmethod
    def get_one_to_many_attributes(df, group_attributes):
        for col in group_attributes:
            for candidate_col in df:
                if candidate_col in group_attributes:
                    continue

                if GroupBy._is_one_to_many(df, col, candidate_col):
                    group_attributes.append(candidate_col)

        return group_attributes

    @staticmethod
    def _is_one_to_many(df, col1, col2):
        if type(df) != pd.DataFrame:
            df = pd.DataFrame(df)
        first_max_cheap_check = df[[col1, col2]].head(1000).groupby(col1).nunique()[col2].max()
        if first_max_cheap_check != 1:
            return False

        first_max = df[[col1, col2]].groupby(col1).nunique()[col2].max()
        return first_max == 1

    def _get_columns_names(self):
        columns = []
        for column in list(self.result_df.columns):
            if isinstance(column, tuple):
                columns.append("_".join(column))
            else:
                if column in self.agg_dict:
                    columns.append(f'{column}_{self.agg_dict[column]}')
                elif isinstance(self.agg_dict, str) and not column.endswith(f'_{self.agg_dict}'):
                    columns.append(f'{column}_{self.agg_dict}')
                else:
                    columns.append(f'{column}')

        return columns

import operator
import pandas as pd
import matplotlib.pyplot as plt
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
        self.cor_deleted_atts = {} 
        self.not_presented = {} 
        self.corr = self.source_df.corr()

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
                figs_in_row: int = DEFAULT_FIGS_IN_ROW, show_scores: bool = False, title: str = None, corr_TH: float = 0.7):
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
        self.delete_correlated_atts(measure, TH = corr_TH)
        figures = measure.calc_influence(utils.max_key(scores), top_k=top_k, figs_in_row=figs_in_row,
                                         show_scores=show_scores, title=title)
        self.correlated_notes(figures, top_k)
        return None
        
        
    def present_deleted_correlated(self, figs_in_row: int = DEFAULT_FIGS_IN_ROW):
        measure = ExceptionalityMeasure()
        measure.calc_influence(deleted = self.not_presented, figs_in_row=figs_in_row)
        
    def correlated_notes(self, figures, top_k):
        txt = ""
        lentxt = 0
        self.not_presented = {}
        for i in range(len(figures)):
            for cor_del in self.cor_deleted_atts.keys():
                if figures[i] == cor_del[1] and i < (top_k-1):
                    lentxt += 1
                    txt += "[" + str(lentxt) + "] " + "The attribute " + cor_del[0] + " is not presented as it correlates with " + cor_del[1] + " (cor: " + str(round(self.corr[cor_del[0]][cor_del[1]],2)) + ")\n"
                    self.not_presented[cor_del[0]] = self.cor_deleted_atts[cor_del]
        if lentxt > 0:
            txt += "\nIn order to view the not presented attributes, please execute the following: df.present_deleted_correlated()"
        plt.figtext(0, 0, txt, horizontalalignment='left',verticalalignment='top')        
    
    def delete_correlated_atts(self, measure, TH = 0.7):
        self.cor_deleted_atts = {}
        corelated_atts = []
        attributes = self.corr.keys()
        numattributes = len(attributes)
        for att in range(numattributes):
            for att1 in range(att,numattributes):
                cor = self.corr[attributes[att]][attributes[att1]]
                if (cor > TH or cor < -TH) and not att==att1:
                    corelated_atts.append([attributes[att],attributes[att1]])
        for cor in corelated_atts:
            if (len(set(cor) - set(measure.score_dict))) == 0:
                if measure.score_dict[cor[0]][2] > measure.score_dict[cor[1]][2]:
                    self.cor_deleted_atts[cor[1], cor[0]] = measure.score_dict[cor[1]]
                    del measure.score_dict[cor[1]]
                else:
                    self.cor_deleted_atts[cor[0], cor[1]] = measure.score_dict[cor[0]]
                    del measure.score_dict[cor[0]]

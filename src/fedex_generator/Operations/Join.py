import pandas as pd

from fedex_generator.commons.consts import TOP_K_DEFAULT, DEFAULT_FIGS_IN_ROW
from fedex_generator.commons import utils
from fedex_generator.commons.DatasetRelation import DatasetRelation
from fedex_generator.Operations import Operation
from fedex_generator.Measures.ExceptionalityMeasure import ExceptionalityMeasure


class Join(Operation.Operation):
    def __init__(self, left_df, right_df, source_scheme, attribute, result_df=None, left_name=None, right_name=None):
        super().__init__(source_scheme)
        self.source_scheme = source_scheme
        self.attribute = attribute

        if result_df is None:
            left_name = utils.get_calling_params_name(left_df)
            right_name = utils.get_calling_params_name(right_df)
            left_df = left_df.copy().reset_index()
            right_df = right_df.copy()
            left_df.columns = [col if col in ["index", attribute] else left_name + "_" + col
                               for col in left_df]
            right_df.columns = [col if col in ["index", attribute] else right_name + "_" + col
                                for col in right_df]
            result_df = pd.merge(left_df, right_df, on=[attribute])

        self.right_name = right_name
        self.left_name = left_name
        self.left_df = left_df
        self.right_df = right_df
        self.result_df = result_df

    def iterate_attributes(self):
        for attr in self.left_df.columns:
            if attr.lower() == "index":
                continue
            yield attr, DatasetRelation(self.left_df, self.result_df, self.left_name)

        for attr in set(self.right_df.columns) - set(self.left_df.columns):
            if attr.lower() == "index":
                continue
            yield attr, DatasetRelation(self.right_df, self.result_df, self.right_name)

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

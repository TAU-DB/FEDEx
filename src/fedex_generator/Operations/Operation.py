from fedex_generator.commons.consts import TOP_K_DEFAULT, DEFAULT_FIGS_IN_ROW


class Operation:
    def __init__(self, scheme):
        self.scheme = scheme
        self.bins_count = 500

    def set_bins_count(self, n):
        self.bins_count = n

    def get_bins_count(self):
        return self.bins_count

    def explain(self, schema=None, attributes=None, top_k=TOP_K_DEFAULT,
                figs_in_row: int = DEFAULT_FIGS_IN_ROW, show_scores: bool = False, title: str = None):
        """
        Explain for operation
        :param schema: dictionary with new columns names, in case {'col_name': 'i'} will be ignored in the explanation
        :param attributes: only this attributes will be included in the explanation calculation
        :param top_k: top k explanations number, default one explanation only.
        :param figs_in_row: number of explanations figs in one row
        :param show_scores: show scores on explanation
        :param title: explanation title


        :return: explain figures
        """
        raise NotImplementedError()

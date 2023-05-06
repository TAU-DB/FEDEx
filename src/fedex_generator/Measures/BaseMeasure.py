import math

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import rc
import numpy as np
import pandas as pd
from paretoset import paretoset

from fedex_generator.Measures.Bins import Bins, Bin
from fedex_generator.commons.consts import SIGNIFICANCE_THRESHOLD, TOP_K_DEFAULT, DEFAULT_FIGS_IN_ROW
from fedex_generator.commons.utils import is_numeric, to_valid_latex



usetex = matplotlib.checkdep_usetex(True)
print(f"usetex-{usetex}")
rc('text', usetex=usetex)
matplotlib.rcParams.update({'font.size': 16})

START_BOLD = r'$\bf{'
END_BOLD = '}$'


def draw_pie(items_dict: dict, important_item=None):
    labels = items_dict.keys()
    probabilities = [items_dict[item] for item in labels]
    explode = [0.1 if item == important_item else 0 for item in labels]

    fig1, ax1 = plt.subplots()
    ax1.pie(probabilities, explode=explode, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
    ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    plt.show()


def draw_histogram(items_before: list, items_after: list, label: str, title):
    if items_before is None:
        items_before = []
    all_vals = list(set(list(items_before) + list(items_after)))
    if not is_numeric(all_vals):
        if len(items_before) > 0:
            plt.hist([sorted(list(items_before)), sorted(list(items_after))], label=["Before", "After"],
                     color=[u'#ff7f0e', u'#1f77b4'])
        else:
            plt.hist([sorted(list(items_after))], label=["After"])

    else:
        bins = np.linspace(np.min(all_vals), np.max(all_vals), min(40, len(all_vals)))
        if len(items_before) > 0:
            plt.hist([list(items_before), list(items_after)], bins=bins, label=["Before", "After"],
                     color=[u'#ff7f0e', u'#1f77b4'])
        else:
            plt.hist([list(items_after)], bins=bins, label=["After"])

    plt.ylabel('results occurrences count', fontsize=16)
    plt.xlabel(to_valid_latex(label), fontsize=16)
    plt.legend(loc='upper right')
    plt.title(to_valid_latex(title))
    plt.show()


class BaseMeasure(object):
    def __init__(self):
        self.source_dict, self.max_val, self.score_dict, self.operation_object, self.scheme = \
            None, None, None, None, None
        self.bins = {}
        self.bin_func = pd.qcut

    def interestingness_only_explanation(self, source_col, result_col, col_name):
        raise NotImplementedError()

    @staticmethod
    def get_source_and_res_cols(dataset_relation, attr):
        source_col, res_col = dataset_relation.get_source(attr), dataset_relation.get_result(attr)
        res_col = res_col[~res_col.isnull()]
        if source_col is not None:
            source_col = source_col[~source_col.isnull()]

        return source_col, res_col

    def calc_measure(self, operation_object, scheme, use_only_columns):
        self.operation_object = operation_object
        self.score_dict = {}
        self.max_val = -1
        self.scheme = scheme

        for attr, dataset_relation in operation_object.iterate_attributes():
            column_scheme = scheme.get(attr, "ni").lower()
            if column_scheme == "i":
                continue

            if len(use_only_columns) > 0 and attr not in use_only_columns:
                continue

            source_col, res_col = self.get_source_and_res_cols(dataset_relation, attr)
            if len(res_col) == 0:
                continue

            size = operation_object.get_bins_count()

            bin_candidates = Bins(source_col, res_col, size)

            measure_score = -np.inf
            for bin_ in bin_candidates.bins:
                measure_score = max(self.calc_measure_internal(bin_), measure_score)

            self.score_dict[attr] = (
                dataset_relation.get_source_name(), bin_candidates, measure_score, (source_col, res_col))

        self.max_val = max([kl_val for _, _, kl_val, _ in self.score_dict.values()])

        return dict([(attribute, _tuple[2]) for (attribute, _tuple) in self.score_dict.items()])

    def calc_measure_internal(self, _bin: Bin):
        raise NotImplementedError()

    def build_operation_expression(self, source_name):
        """
        Get manipulation expression

        :param source_name: The source df name
        :return: string of the manipulation
        """
        raise NotImplementedError()

    def build_explanation(self, current_bin: Bin, max_col_name, max_value, source_name):
        raise NotImplementedError()

    def get_influence_col(self, col, current_bin: Bin, brute_force):
        bin_values = current_bin.get_bin_values()
        return dict(zip(bin_values, self.calc_influence_col(current_bin)))

    def calc_influence_col(self, current_bin: Bin):
        raise NotImplementedError()

    def get_max_k(self, score_dict, k):
        score_array_keys = list(score_dict.keys())
        score_array = np.array([score_dict[i] for i in score_array_keys])
        max_indices = score_array.argsort()
        unique_max_indexes = []
        influence_vals_max_indexes = []

        for index in max_indices:
            current_index = score_array_keys[index]
            unique_max_indexes.append(current_index)
            influence_vals_max_indexes.append(score_dict[current_index])

        max_indices = unique_max_indexes[-k:][::-1]
        max_influences = influence_vals_max_indexes[-k:][::-1]
        return max_indices, max_influences

    def draw_bar(self, bin_item: Bin, influence_vals: dict = None, title=None, ax=None, score=None,
                 show_scores: bool = False):
        raise NotImplementedError()

    @staticmethod
    def get_significance(influence, influence_vals_list):
        influence_var = np.var(influence_vals_list)
        if influence_var == 0:
            return 0.0
        influence_mean = np.mean(influence_vals_list)

        return (influence - influence_mean) / np.sqrt(influence_var)

    def calc_influence(self, brute_force=False, top_k=TOP_K_DEFAULT,
                       figs_in_row: int = DEFAULT_FIGS_IN_ROW, show_scores: bool = False, title: str = None, deleted = None):###
        if deleted:###
            score_dict = deleted
        else:
            score_dict = self.score_dict
                                    ###            
        score_and_col = [(score_dict[col][2], col, score_dict[col][1], score_dict[col][3])
                         for col in score_dict]
      
                         
        list_scores_sorted = score_and_col
        list_scores_sorted.sort()
        K = top_k ###
        if deleted:
            K = len(deleted.keys())
                        ####
        results_columns = ["score", "significance", "influence", "explanation", "bin", "influence_vals"]
        results = pd.DataFrame([], columns=results_columns)
        figures = []
        for score, max_col_name, bins, _ in list_scores_sorted[:-K - 1:-1]:
            source_name, bins, score, _ = score_dict[max_col_name]
            for current_bin in bins.bins:
                influence_vals = self.get_influence_col(max_col_name, current_bin, brute_force)
                influence_vals_list = np.array(list(influence_vals.values()))

                if np.all(np.isnan(influence_vals_list)):
                    continue

                max_values, max_influences = self.get_max_k(influence_vals, 1)

                for max_value, influence_val in zip(max_values, max_influences):
                    significance = self.get_significance(influence_val, influence_vals_list)
                    if significance < SIGNIFICANCE_THRESHOLD:
                        continue
                    explanation = self.build_explanation(current_bin, max_col_name, max_value, source_name)

                    new_result = dict(zip(results_columns,
                                          [score, significance, influence_val, explanation, current_bin, influence_vals,
                                           current_bin.get_bin_name(), max_col_name]))
                    results = pd.concat([results, pd.DataFrame([new_result])], ignore_index=True)

        results_skyline = results[results_columns[0:2]].astype("float")
        skyline = paretoset(results_skyline, ["diff", "max"])
        explanations = results[skyline]["explanation"]
        bins = results[skyline]["bin"]
        influence_vals = results[skyline]["influence_vals"]
        scores = results[skyline]["score"]

        if len(scores) == 0:
            print(f'{source_name} dataset there is not interesting explanation')
            return

        if K > 1: ###
            rows = math.ceil(len(scores) / figs_in_row)
            fig, axes = plt.subplots(rows, figs_in_row, figsize=(7 * figs_in_row, 8 * rows))
            for ax in axes.reshape(-1):
                ax.set_axis_off()
        else:
            fig, axes = plt.subplots(figsize=(7, 7))

        title = title if title else self.build_operation_expression(source_name)
        fig.suptitle(title, fontsize=20)

        for index, (explanation, current_bin, current_influence_vals, score) in enumerate(
                zip(explanations, bins, influence_vals, scores)):


            fig = self.draw_bar(current_bin, current_influence_vals, title=explanation,
                                ax=axes.reshape(-1)[index] if K > 1 else axes, score=score, show_scores=show_scores) ###
            if fig:
                figures.append(fig)

        plt.tight_layout()
        return figures if len(figures) > 0 else fig

    def calc_interestingness_only(self):
        score_and_col = [(self.score_dict[col][2], col, self.score_dict[col][1], self.score_dict[col][3])
                         for col in self.score_dict]
        list_scores_sorted = score_and_col
        list_scores_sorted.sort()
        _, col_name, bins, cols = list_scores_sorted[-1]
        io_explanation = self.interestingness_only_explanation(cols[0],
                                                               cols[1],
                                                               col_name)

        draw_histogram(cols[0], cols[1], col_name, io_explanation)

import pandas as pd
import numpy as np
from utils import is_numeric, to_valid_latex
from Measures.Bins import Bins, Bin, NumericBin
from paretoset import paretoset
import matplotlib.pyplot as plt
from matplotlib import rc
import matplotlib
usetex = matplotlib.checkdep_usetex(True)
print(f"usetex-{usetex}")
rc('text', usetex=usetex)
matplotlib.rcParams.update({'font.size': 16})


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
            plt.hist([sorted(list(items_before)), sorted(list(items_after))], label=["Before", "After"], color=[u'#ff7f0e', u'#1f77b4'])
        else:
            plt.hist([sorted(list(items_after))], label=["After"])

    else:
        bins = np.linspace(np.min(all_vals), np.max(all_vals), min(40, len(all_vals)))
        if len(items_before) > 0:
            plt.hist([list(items_before), list(items_after)], bins=bins, label=["Before", "After"], color=[u'#ff7f0e', u'#1f77b4'])
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

    def calc_measure(self, operation_object, scheme):
        self.operation_object = operation_object
        self.score_dict = {}
        self.max_val = -1
        self.scheme = scheme

        for attr, dataset_relation in operation_object.iterate_attributes():
            column_scheme = scheme.get(attr, "ni").lower()
            if column_scheme == "i":
                continue

            source_col, res_col = self.get_source_and_res_cols(dataset_relation, attr)
            if len(res_col) == 0:
                continue

            size = operation_object.get_bins_count()

            bin_candidates = Bins(source_col, res_col, size)

            measure_score = -np.inf
            for bin_ in bin_candidates.bins:
                measure_score = max(self.calc_measure_internal(bin_), measure_score)

            self.score_dict[attr] = (dataset_relation.get_source_name(), bin_candidates, measure_score, (source_col, res_col))

        self.max_val = max([kl_val for _, _, kl_val, _ in self.score_dict.values()])

        return dict([(attribute, _tuple[2]) for (attribute, _tuple) in self.score_dict.items()])

    def calc_measure_internal(self, _bin: Bin):
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

    def draw_bar(self, bin_item: Bin, influence_vals: dict = None, title=None):
        raise NotImplementedError()

    @staticmethod
    def get_significance(influence, influence_vals_list):
        influence_var = np.var(influence_vals_list)
        if influence_var == 0:
            return 0.0
        influence_mean = np.mean(influence_vals_list)

        return (influence - influence_mean) / np.sqrt(influence_var)

    def calc_influence(self, brute_force=False):
        score_and_col = [(self.score_dict[col][2], col, self.score_dict[col][1], self.score_dict[col][3])
                         for col in self.score_dict]
        list_scores_sorted = score_and_col
        list_scores_sorted.sort()
        K = 3
        results_columns = ["score", "significance", "influence", "explanation", "bin", "influence_vals", "bin_name", "column_name"]
        results = pd.DataFrame([], columns=results_columns)
        figures = []
        for score, max_col_name, bins, _ in list_scores_sorted[:-K-1:-1]:
            source_name, bins, score, _ = self.score_dict[max_col_name]
            for current_bin in bins.bins:
                influence_vals = self.get_influence_col(max_col_name, current_bin, brute_force)
                influence_vals_list = np.array(list(influence_vals.values()))

                if np.all(np.isnan(influence_vals_list)):
                    continue

                max_values, max_influences = self.get_max_k(influence_vals, 1)

                for max_value, influence_val in zip(max_values, max_influences):
                    significance = self.get_significance(influence_val, influence_vals_list)
                    explanation = self.build_explanation(current_bin, max_col_name, max_value, source_name)

                    new_result = dict(zip(results_columns, [score, significance, influence_val, explanation, current_bin, influence_vals, current_bin.get_bin_name(), max_col_name]))
                    results = results.append([new_result], ignore_index=True)

        results_skyline = results[results_columns[0:2]].astype("float")
        skyline = paretoset(results_skyline, ["max", "max"])
        explanations = results[skyline]["explanation"]
        bins = results[skyline]["bin"]
        influence_vals = results[skyline]["influence_vals"]
        for explanation, current_bin, current_influence_vals in zip(explanations, bins, influence_vals):
            fig = self.draw_bar(current_bin, current_influence_vals, title=explanation)
            figures.append(fig)

        return figures

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

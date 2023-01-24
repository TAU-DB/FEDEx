import numpy as np
import pandas as pd
from scipy import stats

from fedex_generator.Measures.BaseMeasure import BaseMeasure, START_BOLD, END_BOLD
from fedex_generator.Measures.Bins import Bin, MultiIndexBin
from fedex_generator.commons import utils

OP_TO_FUNC = {
    'count': np.sum,
    'sum': np.sum,
    'max': np.max,
    'min': np.min,
    'mean': np.mean,
    'prod': np.prod,
    'sem': stats.sem,
    'var': np.var,
    'std': np.std,
    'median': np.median,
    'first': lambda bin_values: bin_values[0],
    'last': lambda bin_values: bin_values[-1],
    'size': np.sum
}


def draw_bar(x: list, y: list, avg_line=None, items_to_bold=None, head_values=None, xname=None, yname=None, alpha=1.,
             ax=None):
    width = 0.5
    ind = np.arange(len(x))
    x = x if utils.is_numeric(x) else [utils.to_valid_latex(i) for i in x]
    y = y if utils.is_numeric(y) else [utils.to_valid_latex(i) for i in y]
    if items_to_bold is not None:
        items_to_bold = items_to_bold if utils.is_numeric(items_to_bold) else [utils.to_valid_latex(i) for i in
                                                                               items_to_bold]

    bar = ax.bar(ind, y, width, alpha=alpha)
    ax.set_xticks(ind)
    ax.set_xticklabels(tuple([str(i) for i in x]), rotation='vertical')

    if avg_line is not None:
        ax.axhline(avg_line, color='red', linewidth=1)
    if items_to_bold is not None:
        for item in items_to_bold:
            bar[x.index(item)].set_color('green')
    if head_values is not None:
        for i, col in enumerate(bar):
            yval = col.get_height()
            ax.text(col.get_x(), yval + .05, head_values[i])

    if xname is not None:
        ax.set_xlabel(utils.to_valid_latex(xname), fontsize=16)

    if yname is not None:
        ax.set_ylabel(utils.to_valid_latex(yname), fontsize=16)


def flatten_other_indexes(series, main_index):
    df = pd.DataFrame(series)
    df = df.reset_index(main_index)
    index_name = "_".join([ind for ind in df.index.names])
    df.index = df.index.to_flat_index()
    df.index.names = [index_name]
    df = df.set_index(main_index, append=True)
    return df[df.columns[0]]


class DiversityMeasure(BaseMeasure):
    def __init__(self):
        super().__init__()

    def get_agg_func_from_name(self, name):
        operation = name.split("_")[-1].lower()
        if hasattr(pd.Series, operation):
            return getattr(pd.Series, operation)
        elif operation in OP_TO_FUNC:
            return OP_TO_FUNC[operation]

        res = []
        for x in self.operation_object.agg_dict:
            for y in self.operation_object.agg_dict[x]:
                res.append(x + '_' + (y if isinstance(y, str) else y.__name__))
        aggregation_index = res.index(name)
        return list(self.operation_object.agg_dict.values())[0][aggregation_index]

    def draw_bar(self, bin_item: MultiIndexBin, influence_vals: dict = None, title=None, ax=None, score=None,
                 show_scores: bool = False):
        try:
            max_values, max_influence = self.get_max_k(influence_vals, 1)
            max_value = max_values[0]

            res_col = bin_item.get_binned_result_column()
            average = float(utils.smart_round(res_col.mean()))

            agger_function = self.get_agg_func_from_name(res_col.name)
            aggregated_result = res_col.groupby(bin_item.get_bin_name()).agg(agger_function)

            bin_result = bin_item.result_column.copy()
            bin_result = flatten_other_indexes(bin_result, bin_item.get_bin_name())
            smallest_multi_bin = MultiIndexBin(bin_item.source_column, bin_result, 0)
            influences = self.get_influence_col(res_col, smallest_multi_bin, True)
            rc = res_col.reset_index([bin_item.get_bin_name()])

            relevant_items = rc[rc[bin_item.get_bin_name()] == max_value]
            relevant_influences = dict([(k, influences[k]) for k in relevant_items.index])
            max_values, max_influence = self.get_max_k(relevant_influences, 10)
            max_values = sorted(max_values)
            labels = set(aggregated_result.keys())

            MAX_BARS = 25
            if len(labels) > MAX_BARS:
                top_items, _ = self.get_max_k(influence_vals, MAX_BARS)
                labels = sorted(top_items)
            else:
                labels = sorted(labels)

            aggregate_column = [aggregated_result.get(item, 0) for item in labels]
            if show_scores:
                ax.set_title(f'score: {score}\n{utils.to_valid_latex(title)}', fontdict={'fontsize': 14})
            else:
                ax.set_title(utils.to_valid_latex(title), fontdict={'fontsize': 14})

            draw_bar(labels, aggregate_column, aggregated_result.mean(), [max_value],
                     xname=f'{bin_item.get_bin_name()} values', yname=bin_item.get_value_name(), ax=ax)
            ax.set_axis_on()

        except Exception as e:
            columns = bin_item.get_binned_result_column()
            title = self._fix_explanation(title, columns, max_value)
            ax.set_title(utils.to_valid_latex(title))
            max_group_value = list(columns[columns == max_value].to_dict().keys())[0]

            draw_bar(list(columns.index),
                     list(columns),
                     average,
                     [max_group_value],
                     yname=bin_item.get_bin_name(), ax=ax)

            ax.set_axis_on()

    @staticmethod
    def _fix_explanation(explanation, binned_column, max_value):
        """
        Change explanation column to match group by
        :param explanation:  bin explanation
        :param binned_column: bin column
        :param max_value: max value

        :return: new explanation
        """
        max_group_value = list(binned_column[binned_column == max_value].to_dict().keys())[0]
        max_value_name = binned_column.name.replace('_', '\\ ')
        group_by_name = binned_column.to_frame().axes[0].name

        return explanation.replace(f'\'{max_value_name}\'=\'{max_value}\'',
                                   f'\'{group_by_name}\' = \'{max_group_value}\'')

    def interestingness_only_explanation(self, source_col, result_col, col_name):
        return f"After employing the GroupBy operation we can see highly diverse set of values in the column '{col_name}'\n" \
               f"The variance" + \
               (f" was {self.calc_var(source_col)} and now it " if source_col is not None else "") + \
               f" is {self.calc_var(result_col)}"

    def calc_influence_col(self, current_bin: Bin):
        bin_values = current_bin.get_bin_values()
        source_col = current_bin.get_source_by_values(bin_values)
        res_col = current_bin.get_result_by_values(bin_values)
        score_all = self.calc_diversity(source_col, res_col)

        influence = []
        for value in bin_values:
            source_col_only_list = current_bin.get_source_by_values([b for b in bin_values if b != value])
            res_col_only_list = current_bin.get_result_by_values([b for b in bin_values if b != value])

            score_without_bin = self.calc_diversity(source_col_only_list, res_col_only_list)
            influence.append(score_all - score_without_bin)

        return influence

    def calc_var(self, pd_array):
        if utils.is_numeric(pd_array):
            return np.var(pd_array)

        appearances = (pd_array.value_counts()).to_numpy()
        mean = np.mean(appearances)
        return np.sum(np.power(appearances - mean, 2)) / len(appearances)

    def calc_diversity(self, source_col, res_col):
        var_res = self.calc_var(res_col)

        if source_col is not None:
            var_rel = self.calc_var(source_col)
        else:
            var_rel = 1.

        res = (var_res / var_rel) if var_rel != 0 else (0. if var_res == 0 else var_res)
        return 0 if np.isnan(res) else res

    def calc_measure_internal(self, bin: Bin):
        result_column = bin.result_column.dropna()
        if bin.name == "MultiIndexBin":
            operation = self.get_agg_func_from_name(result_column.name)
            result_column = result_column.groupby(bin.get_bin_name()).agg(operation)
        return self.calc_diversity(None if bin.source_column is None else bin.source_column.dropna(),
                                   result_column)

    def build_operation_expression(self, source_name):
        from fedex_generator.Operations.GroupBy import GroupBy
        if isinstance(self.operation_object, GroupBy):
            return f'{source_name}.groupby({self.operation_object.group_attributes})' \
                   f'.agg({self.operation_object.agg_dict})'

    def build_explanation(self, current_bin: Bin, max_col_name, max_value, source_name):
        res_col = current_bin.get_binned_result_column()
        if utils.is_categorical(res_col):
            return ""
        var = self.calc_var(res_col)
        if current_bin.name == "NumericBin":
            max_value_numeric = max_value
        elif current_bin.name == "CategoricalBin":
            max_value_numeric = res_col.value_counts()[max_value]
        elif current_bin.name == "MultiIndexBin":
            bin_values = current_bin.get_result_by_values([max_value])
            operation = self.get_agg_func_from_name(res_col.name)
            max_value_numeric = operation(bin_values)
            max_col_name = current_bin.get_bin_name()
            res_col = res_col.groupby(max_col_name).agg(operation)
            var = self.calc_var(res_col)
        elif current_bin.name == "NoBin":
            result_column = current_bin.get_binned_result_column()
            max_value_numeric = max_value
            max_value = result_column.index[result_column == max_value].tolist()
            max_col_name = result_column.index.name

        elif type(current_bin) == Bin:
            raise Exception("Bin is not supported")
        else:
            raise Exception(f"unknown bin type {current_bin.name}")

        sqr = np.sqrt(var)
        x = ((max_value_numeric - np.mean(res_col)) / sqr) if sqr != 0 else 0

        group_by_text = utils.to_valid_latex(f"'{max_col_name}'='{max_value}'", True)
        proportion = 'low' if x < 0 else 'high'
        proportion_column = utils.to_valid_latex(f"{proportion} '{res_col.name}'", True)

        expl = f"Groups with {START_BOLD}{group_by_text}{END_BOLD} (in green) \n" \
               f"have a relatively {START_BOLD}{proportion_column}{END_BOLD} value:\n" \
               f"{utils.smart_round(np.abs(x))} standard deviation {proportion} than the mean " \
               f"({utils.smart_round(np.mean(res_col))})"

        return expl

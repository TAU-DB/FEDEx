import pandas as pd
from fedex_generator.commons import utils


class Bin(object):
    def __init__(self, source_column, result_column, name):
        self.source_column, self.result_column = source_column, result_column
        self.name = name

    def get_binned_source_column(self):
        return self.source_column

    def get_binned_result_column(self):
        return self.result_column

    def get_source_by_values(self, values):
        source_column = self.get_binned_source_column()
        if source_column is None:
            return None

        return source_column[source_column.isin(values)]

    def get_result_by_values(self, values):
        result_column = self.get_binned_result_column()
        return result_column[result_column.isin(values)]

    def get_bin_values(self):
        source_col = self.get_binned_source_column()
        source_col = [] if source_col is None else source_col
        res_col = self.get_binned_result_column()
        values = list(set(source_col).union(set(res_col)))
        values.sort()

        return list(utils.drop_nan(values))

    def get_bin_name(self):
        return self.result_column.name

    def get_bin_representation(self, item):
        return utils.format_bin_item(item)


class UserBin(Bin):
    def __init__(self, source_column, result_column):
        super().__init__(source_column, result_column, "UserDefined")

    def get_binned_source_column(self):
        raise NotImplementedError()

    def get_binned_result_column(self):
        raise NotImplementedError()

    def get_bin_name(self):
        raise NotImplementedError()

    def get_bin_representation(self, item):
        raise NotImplementedError()


class MultiIndexBin(Bin):
    def __init__(self, source_column, result_column, level_index):
        super().__init__(source_column, result_column, "MultiIndexBin")
        self.level_index = level_index

    def get_source_by_values(self, values):
        if self.source_column is None:
            return None

        return self.source_column[self.source_column.index.isin(values, level=self.level_index)]

    def get_result_by_values(self, values):
        return self.result_column[self.result_column.index.isin(values, level=self.level_index)]

    def get_bin_values(self):
        return list(self.result_column.index.levels[self.level_index])

    def get_base_name(self):
        return self.result_column.index.names[0]

    def get_bin_name(self):
        return self.result_column.index.names[self.level_index]

    def get_value_name(self):
        return self.result_column.name


class NumericBin(Bin):
    def __init__(self, source_column, result_column, size):
        if source_column is not None:
            binned_source_column, bins = pd.qcut(source_column, size, retbins=True, labels=False, duplicates='drop')
            bins = utils.drop_nan(bins)
            if len(bins) > 0:
                bins[0] -= 1  # stupid hack because pandas cut uses (,] boundaries, and the first bin is [,]
            binned_result_column = pd.cut(result_column, bins=bins, labels=False, duplicates='drop')
        else:
            binned_source_column = None
            binned_result_column, bins = pd.qcut(result_column, size, retbins=True, labels=False,
                                                 duplicates='drop')  # .reset_index(drop=True)

        super().__init__(binned_source_column, binned_result_column, "NumericBin")
        self.bins = bins

    def get_binned_source_column(self):
        if self.source_column is None:
            return None

        bins_dict = dict(enumerate(self.bins))
        return self.source_column.map(bins_dict)

    def get_binned_result_column(self):
        bins_dict = dict(enumerate(self.bins))
        return self.result_column.map(bins_dict)

    def get_bin_representation(self, item):
        item_index = list(self.bins).index(item)
        next_item = self.bins[item_index + 1]
        return f"({utils.format_bin_item(item)}, {utils.format_bin_item(next_item)}]"


class CategoricalBin(Bin):
    @staticmethod
    def get_top_k_values(column, k):
        col_values = [(v, k) for (k, v) in column.value_counts().items()]
        col_values.sort(reverse=True)

        return [v for (k, v) in col_values[:k]]

    def __init__(self, source_column, result_column, size):
        self.result_values = self.get_top_k_values(result_column, size - 1)
        id_map_top_k = dict(zip(self.result_values, self.result_values))

        if source_column is not None:
            source_column.map(id_map_top_k)
        result_column.map(id_map_top_k)
        super().__init__(source_column, result_column, "CategoricalBin")

    def get_source_by_values(self, values):
        source_column = self.get_binned_source_column()
        if source_column is None:
            return None

        return source_column[source_column.isin(values) | source_column.isnull()]

    def get_result_by_values(self, values):
        result_column = self.get_binned_result_column()
        return result_column[result_column.isin(values) | result_column.isnull()]

    def get_bin_values(self):
        return self.result_values


class NoBin(Bin):
    def __init__(self, source_column, result_column):
        super().__init__(source_column, result_column, "NoBin")


class Bins(object):
    @staticmethod
    def default_binning_method(source_column, result_column):
        return []

    BIN_SIZES = [5, 10]
    USER_BINNING_METHOD = default_binning_method
    ONLY_USER_BINS = False

    def __init__(self, source_column, result_column, bins_count):
        self.max_bin_count = bins_count
        self.bins = list(Bins.USER_BINNING_METHOD(source_column, result_column))

        if Bins.ONLY_USER_BINS:
            return

        if source_column is None:
            # GroupBy
            self.bins += self.get_multi_index_bins(source_column, result_column, bins_count)
            if len(self.bins) > 0:
                return

        if source_column is not None and len(source_column) == 0 and len(result_column) == 0:
            return

        if utils.is_numeric(result_column):
            self.bins += self.bin_numeric(source_column, result_column, bins_count)
        else:
            self.bins += self.bin_categorical(source_column, result_column, bins_count)

    @staticmethod
    def register_binning_method(method, use_only_user_bins=False):
        Bins.USER_BINNING_METHOD = method
        Bins.ONLY_USER_BINS = use_only_user_bins

    @staticmethod
    def bin_numeric(source_col, res_col, size):
        numeric_bins = []
        for bin_count in Bins.BIN_SIZES:
            if bin_count > size:
                break
            numeric_bins.append(NumericBin(source_col, res_col, bin_count))

        return numeric_bins

    @staticmethod
    def set_numeric_bin_sizes(bin_size_list: list):
        Bins.BIN_SIZES = bin_size_list

    @staticmethod
    def bin_categorical(source_col, res_col, size):
        return [CategoricalBin(source_col, res_col, size)]

    @staticmethod
    def get_multi_index_bins(source_col, res_col, size):
        if type(res_col.index) is not pd.MultiIndex:
            return []

        shortest_level = min(res_col.index.levels, key=len)

        if len(shortest_level) > size:
            # above size limit
            return []

        bins_candidates = []
        for level_index, level in enumerate(res_col.index.levels):
            if len(res_col.index.levels) > 1 and level_index == 0:
                continue
            if 1 < len(level) <= size:
                bins_candidates.append(MultiIndexBin(source_col, res_col, level_index))

        return bins_candidates

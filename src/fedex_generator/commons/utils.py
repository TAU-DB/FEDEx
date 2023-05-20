import inspect
import random
import pandas as pd
import scipy
import statistics
import operator
from enum import Enum
from fedex_generator.commons.kstest import *


def to_valid_latex(string, is_bold: bool = False):
    latex_string = str(string)  # unicode_to_latex(string)
    space = r'\ ' if is_bold else ' '
    return latex_string.replace("&", "\\&").replace("#", "\\#").replace(' ', space).replace("_", space)


def smart_round(number):
    return f"{number:.1f}" if 0 <= number <= 2 else f"{number:.0f}"


def format_bin_item(item):
    if is_categorical(item) or is_date(item):
        return str(item)

    if hasattr(item, "is_integer") and item.is_integer():
        return str(int(item))

    if -1 < item < 1:
        return f"{item:.2f}"

    return f"{item:.1f}"


def max_key(d):
    return max(d.items(), key=operator.itemgetter(1))[0]


def remove_dropped_rows_from_source(source_df, result_df, nan_arr):
    result_df_dropped = result_df[np.isnan(nan_arr)]
    dropped_indices = result_df_dropped.index
    return source_df.drop(dropped_indices)


def translate(df, d=None):
    np_array = pd.DataFrame(df).to_numpy().flatten()
    if d is not None:
        d = dict([(d[i], i) for i in d])
    else:
        d = {}
    # count = max(list(d.values()) + [0])
    out = []
    for i in np_array:
        if i not in d:
            r = random.randint(1, len(df) * 1000)
            while r in d:
                r = random.randint(1, len(df) * 1000)
            d[i] = r
        out.append(d[i])

    d = dict([(d[i], i) for i in d])
    return pd.DataFrame(out), d


def translate_back(arr, d):
    arr = np.array(arr)
    inv_map = {v: k for k, v in d.items()}
    return np.array([inv_map.get(i, np.nan) for i in arr])


# For a single score
def get_normalized_score(raw_score, repo_scores):
    constant = 1.0
    # Add constant to make scores strictly positive
    scores = [s + constant for s in repo_scores if not pd.isnull(s)]

    lmbda = scipy.stats.boxcox_normmax(scores)
    scores = scipy.stats.boxcox(scores, lmbda=lmbda)
    # Perform boxcox to our score (isolated), then reduce mean and divide by std to get z-score
    normalized_score = (scipy.stats.boxcox([raw_score + constant, constant], lmbda=lmbda)[0] - statistics.mean(
        scores)) / statistics.pstdev(scores)
    return normalized_score


# For all repo scores. Assuming no None or nan values
def get_normalized_scores(repo_scores):
    constant = 1.0
    # Add constant to make scores strictly positive
    scores = [s + constant for s in repo_scores]

    lmbda = scipy.stats.boxcox_normmax(scores)
    # boxcox transformation
    scores = scipy.stats.boxcox(scores, lmbda=lmbda)
    # get z-scores
    scores = [(s - statistics.mean(scores)) / statistics.pstdev(scores) for s in scores]
    return scores


def is_name_informative(name):
    import string
    return any([char in string.ascii_letters for char in name])


def get_calling_params_name(item):
    frames = inspect.stack()
    highest_var = None
    for frame in frames[2:]:
        prev_locals = frame[0].f_locals
        for var_name in prev_locals:
            if id(item) == id(prev_locals[var_name]) and is_name_informative(var_name):
                highest_var = var_name

    return highest_var


def get_probability_dict(df):
    df_values = dict(df.value_counts(normalize=True))
    return df_values


NUMERIC_TYPES = ['float64', 'int32', 'int64', 'int', 'datetime64[ns]']
CATEGORICAL_TYPES = ['category', 'object', 'bool', 'tuple']


def drop_nan(array):
    return pd.Series(array).dropna().to_numpy().flatten()


class ArrayType(Enum):
    Categorical = 1
    Numeric = 2
    Unknown = 3


def get_array_type(array_like):
    if np.array(array_like).dtype.name in CATEGORICAL_TYPES or np.array(array_like).dtype.name.startswith('str'):
        return ArrayType.Categorical

    if np.array(array_like).dtype.name in NUMERIC_TYPES:
        return ArrayType.Numeric

    return ArrayType.Unknown


def is_categorical(array_like):
    array_type = get_array_type(array_like)
    if array_type == ArrayType.Categorical:
        return True

    if array_type == ArrayType.Numeric:
        return False

    raise RuntimeError(f"Bad type: {np.array(array_like).dtype.name}")


def is_numeric(array_like):
    return not is_categorical(array_like)


def is_date(item):
    if "date" in str(type(item)):
        return True

    return hasattr(item, 'date') or hasattr(item, 'time')

from measures_code_example import *
import warnings

warnings.filterwarnings("ignore")
pd.set_option('display.max_colwidth', 999)
pd.set_option('display.max_columns', 999)

from Operations import Filter
from Operations import Join
from Operations import GroupBy
from Measures.ExceptionalityMeasure import ExceptionalityMeasure
from Measures.NormalizedDiversityMeasure import NormalizedDiversityMeasure
from enum import Enum
from src.fedex_generator.commons import utils
from IPython.display import display, HTML


def compare_rows(row1, row2):
    return abs(row1["score"] - row2["score"]) + abs(row1["significance"] - row2["significance"])


def get_good_and_bad_examples(df):
    best_row = df.iloc[0]
    worst_row = df.iloc[-1]
    return best_row, worst_row, compare_rows(best_row, worst_row)


class Header(Enum):
    h1 = 1
    h2 = 2
    h3 = 3
    h4 = 4
    h5 = 5
    h6 = 6


def display_bold(string, size: Header = Header.h3):
    display(HTML(f'<{size.name}><span style="color: #0000ff;"><strong>{string}</strong></span><{size.name}>'))


SAMPLE = 5000


def join(dbl, dbl_name, dbr, dbr_name, attr, ignore={}):
    if SAMPLE and max(len(dbl), len(dbr)) > SAMPLE:
        dbl_name = utils.get_calling_params_name(dbl)
        dbr_name = utils.get_calling_params_name(dbr)
        sampled_dbl = dbl.sample(n=SAMPLE) if SAMPLE < len(dbl) else dbl
        sampled_dbr = dbr.sample(n=SAMPLE) if SAMPLE < len(dbr) else dbr
        j_sampled = Join.Join(sampled_dbl, sampled_dbr, ignore, attr, left_name=dbl_name, right_name=dbr_name)

        measure = ExceptionalityMeasure()
        scores = measure.calc_measure(j_sampled, {})
        top_3 = sorted(scores, key=scores.get, reverse=True)[:3]
        ignore = { col:"i" for col in scores if col not in top_3 }

    display_bold(f"SELECT * FROM {dbl_name} INNER JOIN {dbr_name} ON {dbl_name}.{attr}={dbr_name}.{attr};")

    j = Join.Join(dbl, dbr, ignore, attr)
    display(j.result_df)
    measure = ExceptionalityMeasure()
    scores = measure.calc_measure(j, ignore)

    results = measure.calc_influence(max_key(scores))

    return j.result_df


def filter_(db,db_name, attr, op, val, ignore={}):
    display_bold(f"SELECT * FROM {db_name} WHERE {attr} {op} {val};")
    if SAMPLE and len(db) > SAMPLE:
        f_sampled = Filter.Filter(db.sample(n=SAMPLE), ignore, attr, op, val)
        measure = ExceptionalityMeasure()
        scores = measure.calc_measure(f_sampled, {})
        top_3 = sorted(scores, key=scores.get, reverse=True)[:3]
        ignore = { col:"i" for col in scores if col not in top_3 }
    f = Filter.Filter(db, ignore, attr, op, val)

    display(f.result_df)

    measure = ExceptionalityMeasure()
    scores = measure.calc_measure(f, {})

    results = measure.calc_influence(max_key(scores))

    return f.result_df


def group_by(db,db_name, attrs, agg_dict, ignore={}):
    items = ", ".join([f"{func}({attr})" for (attr, funcs) in agg_dict.items() for func in funcs])
    attr_str = ", ".join(attrs)
    display_bold(f"SELECT {items} FROM {db_name} GROUP BY {attr_str};")
    g = GroupBy.GroupBy(db, ignore, attrs, agg_dict)

    display(g.result_df)
    measure = NormalizedDiversityMeasure()
    scores = measure.calc_measure(g, {})

    results = measure.calc_influence(max_key(scores))
    
    return g.result_df


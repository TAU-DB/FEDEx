import pandas as pd
import warnings

warnings.filterwarnings("ignore")

from fedex_generator.Operations import Filter
from fedex_generator.Operations import Join
from fedex_generator.Operations import GroupBy
from fedex_generator.Measures.ExceptionalityMeasure import ExceptionalityMeasure
from fedex_generator.Measures.NormalizedDiversityMeasure import NormalizedDiversityMeasure
from fedex_generator.commons.utils import max_key, get_calling_params_name

SAMPLE = 0


def join(dbl, dbl_name, dbr, dbr_name, attr, ignore={}):
    print(f"SELECT * FROM {dbl_name} INNER JOIN {dbr_name} ON {dbl_name}.{attr}={dbr_name}.{attr};")

    if SAMPLE and max(len(dbl), len(dbr)) > SAMPLE:
        dbl_name = get_calling_params_name(dbl)
        dbr_name = get_calling_params_name(dbr)
        sampled_dbl = dbl.sample(n=SAMPLE) if SAMPLE < len(dbl) else dbl
        sampled_dbr = dbr.sample(n=SAMPLE) if SAMPLE < len(dbr) else dbr
        j_sampled = Join.Join(sampled_dbl, sampled_dbr, ignore, attr, left_name=dbl_name, right_name=dbr_name)

        measure = ExceptionalityMeasure()
        scores = measure.calc_measure(j_sampled, {})
        top_1 = sorted(scores, key=scores.get, reverse=True)[0]
        ignore = {col: "i" for col in scores if col != top_1}
    j = Join.Join(dbl, dbr, ignore, attr)
    print(j.result_df)
    measure = ExceptionalityMeasure()
    scores = measure.calc_measure(j, ignore)
    print(scores)
    results = measure.calc_influence(max_key(scores))
    return j.result_df


def filter_(db, db_name, attr, op, val, ignore={}):
    print(f"SELECT * FROM {db_name} WHERE {attr} {op} {val};")
    if SAMPLE and len(db) > SAMPLE:
        f_sampled = Filter.Filter(db.sample(n=SAMPLE), ignore, attr, op, val)
        measure = ExceptionalityMeasure()
        scores = measure.calc_measure(f_sampled, {})
        top_1 = sorted(scores, key=scores.get, reverse=True)[0]
        ignore = {col: "i" for col in scores if col != top_1}

    f = Filter.Filter(db, ignore, attr, op, val)
    print(f.result_df)
    measure = ExceptionalityMeasure()
    scores = measure.calc_measure(f, ignore)
    results = measure.calc_influence(max_key(scores))


def group_by(db, db_name, attrs, agg_dict, ignore={}):
    items = ", ".join([f"{func}({attr})" for (attr, funcs) in agg_dict.items() for func in funcs])
    attr_str = ", ".join(attrs)
    print(f"SELECT {items} FROM {db_name} GROUP BY {attr_str};")
    g = GroupBy.GroupBy(db, ignore, attrs, agg_dict)
    print(g.result_df)
    measure = NormalizedDiversityMeasure()
    scores = measure.calc_measure(g, {})
    results = measure.calc_influence(max_key(scores))


def main():
    spotify_all = pd.read_csv(r"Datasets/data.csv")

    group_by(spotify_all,
             "spotify",
             ["year"],
             {"popularity": ["mean", "max", "min"]})


if __name__ == "__main__":
    main()

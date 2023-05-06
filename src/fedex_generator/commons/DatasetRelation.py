class DatasetRelation(object):
    def __init__(self, source_df, result_df, source_table_name):
        self.source_df = source_df
        self.result_df = result_df
        self.source_table_name = source_table_name

    def get_source(self, attr):
        # GroupBy
        if self.source_df is None or attr not in self.source_df:
            return None
        return self.source_df[attr]

    def get_result(self, attr):
        return self.result_df[attr]

    def get_source_name(self):
        return self.source_table_name

# exporter.py
import json
import pandas as pd

def dataframe_to_ascii(df):
    df_str = df.astype(str)
    col_widths = {col: max(df_str[col].map(len).max(), len(col)) for col in df_str.columns}

    separator = "+" + "+".join("-" * (col_widths[col] + 2) for col in df_str.columns) + "+"
    header = "|" + "|".join(f" {col.ljust(col_widths[col])} " for col in df_str.columns) + "|"

    rows = [
        "|" + "|".join(f" {str(val).ljust(col_widths[col])} " for col, val in row.items()) + "|"
        for _, row in df_str.iterrows()
    ]

    return "\n".join([separator, header, separator] + rows + [separator])


def dataframe_to_json(df):
    return json.dumps(df.to_dict(orient="records"), indent=4)

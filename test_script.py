import polars as pl
import pandas as pd
import os

df = pd.DataFrame([
    {"cited_1": "https://openalex.org/W1", "cited_2": "https://openalex.org/W2", "co_citation_count": 10},
    {"cited_1": "https://openalex.org/W2", "cited_2": "https://openalex.org/W3", "co_citation_count": 5}
])
os.makedirs("pipeline_results_37k/data", exist_ok=True)
df.to_csv("pipeline_results_37k/data/network_cocitations.csv", index=False)

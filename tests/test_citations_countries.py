import pytest
import pandas as pd
import polars as pl
import numpy as np
from src.core.countries import CountryAnalysis
from src.core.citations import CitationsAnalysis

def test_country_evolution_extraction():
    analyzer = CountryAnalysis()
    
    # Create a dummy DataFrame with diverse country affiliations
    df = pl.DataFrame([
        {
            "Title": "Paper A",
            "Year": 2020,
            "Affiliations": "University of Maryland, Baltimore, MD, USA; Orange, France"
        },
        {
            "Title": "Paper B",
            "Year": 2020,
            "Affiliations": "Institut national de recherche, Paris, France"
        },
        {
            "Title": "Paper C",
            "Year": 2021,
            "Affiliations": "Tsinghua University, Beijing, PRC"
        }
    ])
    
    exploded, evolution = analyzer.process_countries(df)
    
    assert not exploded.empty
    assert not evolution.empty
    
    # Paper A has United States and France, Paper B has France -> Total France in 2020 = 2, USA = 1
    # Paper C has China in 2021 -> China = 1
    france_2020 = evolution[(evolution["Year"] == 2020) & (evolution["Country"] == "France")]["Count"].values[0]
    usa_2020 = evolution[(evolution["Year"] == 2020) & (evolution["Country"] == "United States")]["Count"].values[0]
    china_2021 = evolution[(evolution["Year"] == 2021) & (evolution["Country"] == "China")]["Count"].values[0]
    
    assert france_2020 == 2
    assert usa_2020 == 1
    assert china_2021 == 1

def test_co_citation_and_coupling():
    analyzer = CitationsAnalysis()
    
    # Create dummy references dataframe
    # source_1 cites dest_A and dest_B
    # source_2 cites dest_A and dest_B
    # source_3 cites dest_A only
    ref_df = pd.DataFrame([
        {"source": "src_1", "destination": "dest_A", "authors": "Author A", "year": 2010},
        {"source": "src_1", "destination": "dest_B", "authors": "Author B", "year": 2012},
        {"source": "src_2", "destination": "dest_A", "authors": "Author A", "year": 2010},
        {"source": "src_2", "destination": "dest_B", "authors": "Author B", "year": 2012},
        {"source": "src_3", "destination": "dest_A", "authors": "Author A", "year": 2010},
    ])
    
    results, X = analyzer.calculate_co_citation(ref_df)
    
    assert not results.empty
    assert X is not None
    
    # dest_A and dest_B are co-cited by src_1 and src_2 -> co-citation count should be 2!
    pair = results[((results["cited_1"] == "dest_A") & (results["cited_2"] == "dest_B")) |
                   ((results["cited_1"] == "dest_B") & (results["cited_2"] == "dest_A"))]
                   
    assert len(pair) == 1
    assert pair["co_citation_count"].values[0] == 2
    assert pair["authors_1"].values[0] in ("Author A", "Author B")
    assert pair["year_1"].values[0] in (2010, 2012)
    
    # Test bibliographic coupling
    # src_1 and src_2 both cite dest_A and dest_B -> coupling weight should be 2!
    source_codes, source_uniques = pd.factorize(ref_df['source'].drop_duplicates())
    coupling = analyzer.calculate_bibliographic_coupling(X, source_uniques)
    
    assert not coupling.empty
    c_pair = coupling[((coupling["source_1"] == "src_1") & (coupling["source_2"] == "src_2")) |
                     ((coupling["source_1"] == "src_2") & (coupling["source_2"] == "src_1"))]
                     
    assert len(c_pair) == 1
    assert c_pair["coupling_weight"].values[0] == 2

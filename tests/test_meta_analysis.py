import pytest
import pandas as pd
import numpy as np
import os
from src.core.meta_analysis import EffectSizeSynthesizer
from src.core.extraction import VariableExtractor, StudyData
from src.core.fulltext.parser import PDFParser
from src.core.viz import Visualization

def test_effect_size_synthesizer_basic():
    synthesizer = EffectSizeSynthesizer()
    
    # Create synthetic study data (Cohen's d and Sample size)
    data = {
        "Title": ["Study A", "Study B", "Study C", "Study D", "Study E"],
        "Authors": ["Smith, J.", "Doe, A.", "Johnson, M.", "Lee, K.", "Wang, L."],
        "Year": [2020, 2021, 2021, 2022, 2023],
        "meta_effect_size_d": [0.45, 0.60, 0.35, 0.70, 0.50],
        "meta_sample_size": [50, 80, 40, 100, 60]
    }
    df = pd.DataFrame(data)
    
    results, augmented_df = synthesizer.run_meta_analysis(df)
    
    assert results["k_studies"] == 5
    assert "fixed_effects" in results
    assert "random_effects" in results
    assert "heterogeneity" in results
    assert "publication_bias" in results
    
    # Check that pooled effect estimate is reasonable (between 0.35 and 0.70)
    fe_est = results["fixed_effects"]["estimate"]
    re_est = results["random_effects"]["estimate"]
    assert 0.35 <= fe_est <= 0.70
    assert 0.35 <= re_est <= 0.70
    
    # Check confidence intervals
    assert results["fixed_effects"]["ci_lower"] < fe_est < results["fixed_effects"]["ci_upper"]
    assert results["random_effects"]["ci_lower"] < re_est < results["random_effects"]["ci_upper"]
    
    # Check heterogeneity metrics
    assert results["heterogeneity"]["i_squared_pct"] >= 0.0
    assert results["heterogeneity"]["tau_squared"] >= 0.0
    
    # Check augmented columns for plotting
    assert "v_i" in augmented_df.columns
    assert "w_i" in augmented_df.columns

def test_effect_size_synthesizer_insufficient_data():
    synthesizer = EffectSizeSynthesizer()
    df_empty = pd.DataFrame()
    res_empty, _ = synthesizer.run_meta_analysis(df_empty)
    assert res_empty == {}

    df_one = pd.DataFrame({
        "meta_effect_size_d": [0.5],
        "meta_sample_size": [30]
    })
    res_one, _ = synthesizer.run_meta_analysis(df_one)
    assert res_one["k"] == 1

def test_variable_extractor_text():
    extractor = VariableExtractor()
    
    sample_text = (
        "In this study, N = 64 patients were evaluated. The experiment was double-blind and randomized. "
        "We observed a significant improvement with Cohen's d = 0.58 and accuracy of 92.5%. "
        "The mean score was M = 45.2 with standard deviation SD = 6.4. "
        "No participant attrition or drop-out was observed."
    )
    
    data = extractor.extract_from_text(sample_text)
    
    assert data.sample_size == 64
    assert data.effect_size_d == 0.58
    assert data.accuracy == 0.925
    assert data.mean == 45.2
    assert data.std_dev == 6.4
    assert data.is_randomized is True
    assert data.is_blinded is True
    assert data.attrition_reported is True

def test_variable_extractor_dataframe():
    extractor = VariableExtractor()
    df = pd.DataFrame([
        {"Title": "Paper 1", "Abstract": "A total of 50 participants participated in this randomized trial."},
        {"Title": "Paper 2", "Abstract": "We tested n=120 subjects achieving accuracy of 88.0%."}
    ])
    
    df_out = extractor.extract_dataframe(df, text_cols=["Abstract"])
    assert "meta_sample_size" in df_out.columns
    assert "meta_is_randomized" in df_out.columns
    assert df_out["meta_sample_size"].iloc[0] == 50
    assert bool(df_out["meta_is_randomized"].iloc[0]) is True
    assert df_out["meta_sample_size"].iloc[1] == 120

def test_pdf_parser_fallback():
    parser = PDFParser()
    res = parser.parse_pdf("non_existent_file.pdf")
    assert res["abstract"] == ""
    assert res["methodology"] == ""
    assert res["results"] == ""

def test_meta_analysis_visualizations(tmp_path):
    viz = Visualization()
    
    data = {
        "Authors": ["Smith, J.", "Doe, A.", "Lee, K."],
        "Year": [2020, 2021, 2022],
        "meta_effect_size_d": [0.45, 0.60, 0.35],
        "v_i": [0.08, 0.05, 0.10]
    }
    df = pd.DataFrame(data)
    meta_results = {
        "random_effects": {
            "estimate": 0.50,
            "ci_lower": 0.30,
            "ci_upper": 0.70
        }
    }
    
    forest_pdf = str(tmp_path / "forest.pdf")
    fig_forest = viz.plot_forest(df, meta_results, save_path=forest_pdf)
    assert fig_forest is not None
    assert os.path.exists(forest_pdf)
    
    funnel_pdf = str(tmp_path / "funnel.pdf")
    fig_funnel = viz.plot_funnel(df, save_path=funnel_pdf)
    assert fig_funnel is not None
    assert os.path.exists(funnel_pdf)
    
    prisma_metrics = {
        "identified": 1200,
        "screened": 850,
        "eligible": 150,
        "included": 45,
        "exclusion_reasons": {"Not EEG/BCI": 700}
    }
    prisma_pdf = str(tmp_path / "prisma.pdf")
    fig_prisma = viz.plot_prisma_flowchart(prisma_metrics, save_path=prisma_pdf)
    assert fig_prisma is not None
    assert os.path.exists(prisma_pdf)

def test_pdf_retriever_filter_candidates():
    from src.core.fulltext.retriever import PDFRetriever
    retriever = PDFRetriever()
    
    df = pd.DataFrame([
        {"Title": "Paper A", "DOI": "10.1016/j.a", "Cite Count": 15, "Author Keywords": "EEG; Noise removal", "relevance_score": 0.8},
        {"Title": "Paper B", "DOI": "10.1109/j.b", "Cite Count": 2, "Author Keywords": "fMRI; vision", "relevance_score": 0.2},
        {"Title": "Paper C", "DOI": "10.1038/j.c", "Cite Count": 50, "Author Keywords": "BCI; artifact reduction", "relevance_score": 0.9},
    ])
    
    # Test citation filter
    cands_cit = retriever.filter_candidates(df, min_citations=10)
    assert len(cands_cit) == 2
    assert "Paper B" not in cands_cit["Title"].values
    
    # Test keywords filter
    cands_kw = retriever.filter_candidates(df, required_keywords=["noise", "artifact"])
    assert len(cands_kw) == 2
    assert "Paper B" not in cands_kw["Title"].values
    
    # Test max_papers limit
    cands_max = retriever.filter_candidates(df, max_papers=1)
    assert len(cands_max) == 1
    assert cands_max.iloc[0]["Title"] == "Paper C"

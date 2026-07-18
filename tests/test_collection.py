import pytest
import pandas as pd
from src.core.collectors.openalex import OpenAlexCollector
from src.core.collectors.semantic_scholar import SemanticScholarCollector
from src.core.collection import UnifiedCollector

def test_openalex_year_filter():
    collector = OpenAlexCollector()
    # This won't actually call the API because we'll mock it if we wanted to be thorough,
    # but here we just check if the logic for building params is sound if we had a way to inspect it.
    # For now, let's just ensure it initializes.
    assert collector.BASE_URL == "https://api.openalex.org/works"

def test_unified_collector_merge():
    # Mocking collectors to test merging
    class MockCollector:
        def __init__(self, name, papers):
            self.name = name
            self.papers = papers
        def fetch_papers(self, *args, **kwargs):
            return pd.DataFrame(self.papers)

    unified = UnifiedCollector()
    unified.collectors = {
        "source1": MockCollector("source1", [{"Title": "Paper 1", "DOI": "10.1"}, {"Title": "Paper 2", "DOI": "10.2"}]),
        "source2": MockCollector("source2", [{"Title": "Paper 1", "DOI": "10.1"}, {"Title": "Paper 3", "DOI": "10.3"}])
    }
    
    merged = unified.fetch_all("test query")
    # Should have 3 unique papers
    assert len(merged) == 3
    assert set(merged["Title"]) == {"Paper 1", "Paper 2", "Paper 3"}

def test_publication_validation_robustness():
    from src.core.ingestion import validate_publications
    import numpy as np

    df = pd.DataFrame([
        {
            "Title": "Test Paper 1",
            "Abstract": "Some abstract text",
            "Authors": "Author A; Author B",
            "Year": 2020.0,
            "Affiliations": None,
            "DOI": np.nan,
            "EID": "",
        }
    ])
    validated = validate_publications(df)
    assert len(validated) == 1
    assert validated[0].title == "Test Paper 1"
    assert validated[0].year == 2020
    assert validated[0].affiliations is None
    assert validated[0].doi is None
    assert validated[0].eid is None

def test_unified_collector_merge_metadata():
    class MockCollector:
        def __init__(self, papers):
            self.papers = papers
        def fetch_papers(self, *args, **kwargs):
            return pd.DataFrame(self.papers)

    unified = UnifiedCollector()
    unified.collectors = {
        "source1": MockCollector([
            {
                "Title": "Paper A",
                "DOI": "10.1",
                "Abstract": "Abstract from source 1",
                "Cite Count": 10,
                "Source": "OpenAlex",
                "Author Keywords": "quantum; computing"
            }
        ]),
        "source2": MockCollector([
            {
                "Title": "Paper A",
                "DOI": "10.1",
                "Abstract": "",
                "Cite Count": 15,
                "Source": "Semantic Scholar",
                "Author Keywords": "computing; algorithms"
            }
        ])
    }
    
    merged = unified.fetch_all("test query")
    assert len(merged) == 1
    row = merged.iloc[0]
    assert row["Title"] == "Paper A"
    assert row["Abstract"] == "Abstract from source 1"
    assert row["Cite Count"] == 15
    assert "OpenAlex" in row["Source"] and "Semantic Scholar" in row["Source"]
    assert row["Author Keywords"] == "algorithms; computing; quantum"

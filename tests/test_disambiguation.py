import pytest
import pandas as pd
from src.core.disambiguation import AuthorDisambiguator

def test_author_affiliation_pairing_cases():
    dis = AuthorDisambiguator()

    # Case 1: 1 affiliation on paper -> all co-authors share it
    authors = "Smith, John; Doe, Jane"
    affils = "Stanford University"
    pairs = dis.pair_authors_and_affiliations(authors, affils)
    assert len(pairs) == 2
    assert pairs[0]["author_base_name"] == "Smith, John"
    assert pairs[0]["affiliation"] == "Stanford University"
    assert pairs[0]["role"] == "fa"
    assert pairs[1]["author_base_name"] == "Doe, Jane"
    assert pairs[1]["affiliation"] == "Stanford University"
    assert pairs[1]["role"] == "mp"

    # Case 2: Exact 1-to-1 match (N authors == M affiliations)
    authors_2 = "Wu, Lingyun; Hu, Zhiwen; Liu, Jing"
    affils_2 = "Tsinghua University; Peking University; Fudan University"
    pairs_2 = dis.pair_authors_and_affiliations(authors_2, affils_2)
    assert len(pairs_2) == 3
    assert pairs_2[0]["affiliation"] == "Tsinghua University"
    assert pairs_2[0]["role"] == "fa"
    assert pairs_2[1]["affiliation"] == "Peking University"
    assert pairs_2[1]["role"] == "coauthor"
    assert pairs_2[2]["affiliation"] == "Fudan University"
    assert pairs_2[2]["role"] == "mp"

def test_author_id_extraction():
    dis = AuthorDisambiguator()
    authors = "Wu, Lingyun (57226766385); Hu, Zhiwen (59220407300)"
    affils = "Tsinghua University; Peking University"
    pairs = dis.pair_authors_and_affiliations(authors, affils)
    assert pairs[0]["author_id"] == "57226766385"
    assert pairs[0]["author_base_name"] == "Wu, Lingyun"
    assert pairs[1]["author_id"] == "59220407300"
    assert pairs[1]["author_base_name"] == "Hu, Zhiwen"

def test_dataset_disambiguation_homonyms():
    dis = AuthorDisambiguator()
    df = pd.DataFrame([
        {"Title": "Paper 1", "Authors": "Wang, Y.; Smith, J.", "Affiliations": "MIT, USA; Harvard, USA"},
        {"Title": "Paper 2", "Authors": "Wang, Y.; Zhang, L.", "Affiliations": "Oxford University, UK; Cambridge, UK"},
    ])
    df_out, mapping = dis.disambiguate_dataset(df)
    assert "Disambiguated Authors" in df_out.columns
    dis_row0 = df_out["Disambiguated Authors"].iloc[0]
    dis_row1 = df_out["Disambiguated Authors"].iloc[1]

    # Wang, Y. from MIT should be distinguished from Wang, Y. from Oxford
    assert "MIT" in dis_row0 or "Wang, Y." in dis_row0
    assert "Oxford" in dis_row1 or "Wang, Y." in dis_row1

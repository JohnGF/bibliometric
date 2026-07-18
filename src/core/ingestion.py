import pandas as pd
import polars as pl
import pycountry
import re
from typing import List, Optional
from pydantic import BaseModel, Field, validator

# --- Pydantic Schema ---


class PublicationSchema(BaseModel):
    title: str = Field(..., alias="Title")
    abstract: Optional[str] = Field(None, alias="Abstract")
    authors: Optional[str] = Field(None, alias="Authors")
    author_keywords: Optional[str] = Field(None, alias="Author Keywords")
    index_keywords: Optional[str] = Field(None, alias="Index Keywords")
    year: Optional[int] = Field(None, alias="Year")
    source_title: Optional[str] = Field(None, alias="Source title")
    affiliations: Optional[str] = Field(None, alias="Affiliations")
    doi: Optional[str] = Field(None, alias="DOI")
    eid: Optional[str] = Field(None, alias="EID")
    references: Optional[str] = Field(None, alias="References")

    @validator("abstract", "authors", "author_keywords", "index_keywords", "source_title", "affiliations", "doi", "eid", "references", pre=True)
    def parse_strings(cls, v):
        if pd.isna(v) or v == "":
            return None
        return str(v)

    @validator("year", pre=True)
    def parse_year(cls, v):
        if pd.isna(v) or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class ReferenceSchema(BaseModel):
    source_eid: str = Field(..., alias="Source EID")
    target_eid: str = Field(..., alias="Target EID")
    relationship_type: str = Field("citation", alias="Type")


def validate_publications(df: pd.DataFrame) -> List[PublicationSchema]:
    records = df.to_dict(orient="records")
    return [PublicationSchema(**record) for record in records]


def validate_references(df: pd.DataFrame) -> List[ReferenceSchema]:
    records = df.to_dict(orient="records")
    return [ReferenceSchema(**record) for record in records]


COUNTRIES = [country.name for country in pycountry.countries]
COUNTRY_CODES = [country.alpha_2 for country in pycountry.countries]
COUNTRY_CODE_MAP = {code: name for code, name in zip(COUNTRY_CODES, COUNTRIES)}
COUNTRY_CODE_MAP.update(
    {
        "USA": "United States",
        "UK": "United Kingdom",
        "UAE": "United Arab Emirates",
        "HK": "Hong Kong",
        "PRC": "China",
    }
)

US_STATE_CODES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]

COMMON_NAMES = {
    "Iran, Islamic Republic of": "Iran",
    "Korea, Republic of": "South Korea",
    "Korea, Democratic People's Republic of": "North Korea",
    "Holy See": "Vatican",
}

COUNTRY_NAME_VARIANTS = {
    "Iran": "Iran, Islamic Republic of",
    "South Korea": "Korea, Republic of",
    "North Korea": "Korea, Democratic People's Republic of",
    "Vatican": "Holy See",
}


def extract_countries(affiliation: str) -> List[str]:
    if not isinstance(affiliation, str):
        return []

    affiliations = re.split(r";", affiliation)
    unique_affiliations = list(set(affiliations))
    countries_found = set()

    for affil in unique_affiliations:
        affil = affil.strip()
        parts = re.split(r",", affil)

        for part in reversed(parts):
            part_clean = part.strip().upper()
            if part_clean in US_STATE_CODES:
                countries_found.add("United States")
                break

            for code, name in COUNTRY_CODE_MAP.items():
                if code.upper() == part_clean:
                    countries_found.add(name)
                    break

            part_stripped = part.strip()
            official_name = COUNTRY_NAME_VARIANTS.get(part_stripped, part_stripped)
            if official_name in COUNTRIES:
                common_name = COMMON_NAMES.get(official_name, official_name)
                countries_found.add(common_name)
                break

            for country in COUNTRIES:
                if country.lower() == part_stripped.lower():
                    common_name = COMMON_NAMES.get(country, country)
                    countries_found.add(common_name)
                    break

    return list(countries_found)


# --- Data Loading ---


def load_data(file_path: str) -> pd.DataFrame:
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    elif file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
    elif file_path.endswith(".parquet"):
        df = pd.read_parquet(file_path)
    else:
        raise ValueError("Unsupported file format")

    return df


def validate_data(df: pd.DataFrame) -> List[PublicationSchema]:
    # Convert dataframe to list of dicts and validate with Pydantic
    records = df.to_dict(orient="records")
    return [PublicationSchema(**record) for record in records]

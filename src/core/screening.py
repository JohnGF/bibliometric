import logging
import json
import urllib.request
import urllib.error
import pandas as pd
from typing import Optional, List, Dict
import torch

logger = logging.getLogger(__name__)

# Lazy import for sentence_transformers
try:
    from sentence_transformers import SentenceTransformer, util
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


DEFAULT_EEG_BCI_TARGET_PROMPT = (
    "EEG brain computer interface motor decoding signal processing "
    "denoising noise information feature extraction electroencephalography"
)


def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    col_map = {col.lower().strip(): col for col in df.columns}
    for cand in candidates:
        cand_lower = cand.lower().strip()
        if cand_lower in col_map:
            return col_map[cand_lower]
    return None


class EmbeddingRelevanceFilter:
    """Option 1: Vector embedding semantic similarity filter using SentenceTransformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", target_prompt: str = DEFAULT_EEG_BCI_TARGET_PROMPT):
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers is required for EmbeddingRelevanceFilter. "
                "Please install it via `pip install sentence-transformers`."
            )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"EmbeddingRelevanceFilter: Loading model '{model_name}' on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.target_prompt = target_prompt
        self.target_embedding = self.model.encode(self.target_prompt, convert_to_tensor=True)

    def filter_dataframe(
        self,
        df: pd.DataFrame,
        threshold: float = 0.35,
        title_col: Optional[str] = None,
        abstract_col: Optional[str] = None
    ) -> pd.DataFrame:
        """Filters a DataFrame of publications based on semantic relevance threshold."""
        if df.empty:
            return df

        resolved_title_col = title_col or _find_col(df, ["Title", "title", "paper_title", "headline", "name"])
        resolved_abstract_col = abstract_col or _find_col(df, ["Abstract", "abstract", "summary", "description"])

        if not resolved_title_col and not resolved_abstract_col:
            logger.warning("No Title or Abstract column found in DataFrame. Skipping embedding relevance filtering.")
            return df

        titles = df[resolved_title_col].fillna("").astype(str) if resolved_title_col else pd.Series([""] * len(df), index=df.index)
        abstracts = df[resolved_abstract_col].fillna("").astype(str) if resolved_abstract_col else pd.Series([""] * len(df), index=df.index)
        
        texts = (titles + ". " + abstracts).tolist()

        logger.info(f"Computing embeddings for {len(texts)} papers...")
        doc_embeddings = self.model.encode(texts, convert_to_tensor=True, batch_size=64, show_progress_bar=False)

        similarities = util.cos_sim(doc_embeddings, self.target_embedding).cpu().numpy().flatten()
        
        df_out = df.copy()
        df_out["relevance_score"] = similarities

        retained_df = df_out[df_out["relevance_score"] >= threshold].copy()
        dropped_count = len(df_out) - len(retained_df)
        logger.info(
            f"Embedding Relevance Filtering Complete: Retained {len(retained_df)}/{len(df_out)} papers "
            f"(threshold={threshold}, dropped {dropped_count} low-similarity papers)."
        )

        return retained_df


class LLMRelevanceClassifier:
    """Option 2: LLM-based zero-shot classifier & noise paradigm extractor."""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model

    def classify_paper(self, title: str, abstract: str) -> Dict:
        """Classifies a single paper's relevance and noise treatment paradigm."""
        prompt = f"""
Analyze this research paper title and abstract for an EEG Brain-Computer Interface (BCI) bibliometric study.

Title: {title}
Abstract: {abstract}

Return ONLY raw JSON with these exact keys:
- "is_bci": boolean (true if about EEG, BCI, motor imagery, or motor decoding; false otherwise)
- "noise_paradigm": string (must be one of: "filtering_removal", "noise_as_information", "robust_decoding", "unspecified")

JSON response:
"""
        req_data = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    return json.loads(body.get("response", "{}"))
        except Exception as e:
            logger.warning(f"LLM Classification failed for title '{title[:30]}...': {e}")
        
        return {"is_bci": True, "noise_paradigm": "unspecified"}

    def categorize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies LLM classification across a DataFrame of papers."""
        if df.empty:
            return df

        title_col = _find_col(df, ["Title", "title", "paper_title", "headline", "name"])
        abstract_col = _find_col(df, ["Abstract", "abstract", "summary", "description"])

        if not title_col and not abstract_col:
            logger.warning("No Title or Abstract column found in DataFrame. Skipping LLM categorization.")
            return df

        logger.info(f"LLM Categorization: Processing {len(df)} papers with model '{self.model}'...")
        
        is_bci_list = []
        noise_paradigms = []

        for idx, row in df.iterrows():
            title = str(row[title_col]) if title_col and not pd.isna(row[title_col]) else ""
            abstract = str(row[abstract_col]) if abstract_col and not pd.isna(row[abstract_col]) else ""
            res = self.classify_paper(title, abstract)
            is_bci_list.append(res.get("is_bci", True))
            noise_paradigms.append(res.get("noise_paradigm", "unspecified"))

        df_out = df.copy()
        df_out["is_bci_relevant"] = is_bci_list
        df_out["noise_paradigm"] = noise_paradigms
        
        return df_out


class PaperScreener:
    """Unified Paper Screener supporting both Option 1 (Embeddings) and Option 2 (LLM)."""

    def __init__(
        self,
        use_embedding_filter: bool = True,
        embedding_threshold: float = 0.35,
        use_llm_categorization: bool = False,
        llm_model: str = "llama3.2:3b",
        ollama_url: str = "http://localhost:11434"
    ):
        self.use_embedding_filter = use_embedding_filter
        self.embedding_threshold = embedding_threshold
        self.use_llm_categorization = use_llm_categorization
        
        self.embedding_filter = EmbeddingRelevanceFilter() if use_embedding_filter else None
        self.llm_classifier = LLMRelevanceClassifier(ollama_url=ollama_url, model=llm_model) if use_llm_categorization else None

    def screen(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        # Step 1: Option 1 - Fast Embedding Relevance Filter
        if self.use_embedding_filter and self.embedding_filter:
            df = self.embedding_filter.filter_dataframe(df, threshold=self.embedding_threshold)

        # Step 2: Option 2 - LLM Noise Paradigm Categorization
        if self.use_llm_categorization and self.llm_classifier:
            df = self.llm_classifier.categorize_dataframe(df)

        return df

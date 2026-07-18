import polars as pl
import pandas as pd
from bertopic import BERTopic
from typing import List, Dict, Optional
import numpy as np
import logging

# GPU Detection
try:
    import torch
    HAS_TORCH_CUDA = torch.cuda.is_available()
    if HAS_TORCH_CUDA:
        try:
            from cuml.cluster import HDBSCAN
            from cuml.manifold import UMAP
            HAS_RAPIDS_CUML = True
        except ImportError:
            HAS_RAPIDS_CUML = False
    else:
        HAS_RAPIDS_CUML = False
except Exception:
    HAS_TORCH_CUDA = False
    HAS_RAPIDS_CUML = False

# --- Default Mapping (Extracted from Keyword.ipynb) ---

DEFAULT_TERM_MAPPING = {
    "bci": "brain-computer interface",
    "brain-computer interface (bci)": "brain-computer interface",
    "brain computer interface (bci)": "brain-computer interface",
    "brain computer interface": "brain-computer interface",
    "affective brain-computer interface": "brain-computer interface",
    "brain–computer interfaces": "brain-computer interface",
    "brain–computer interface": "brain-computer interface",
    "brain-computer interfaces": "brain-computer interface",
    "brain–computer interface (bci)": "brain-computer interface",
    "motor imagery (mi)": "motor imagery",
    "erp": "event-related potentials",
    "event-related potential": "event-related potentials",
    "steady-state visual evoked potential": "ssvep",
    "cnn": "convolutional neural network",
    "electrocardiography": "ecg",
    "electromyography": "emg",
    "convolutional neural network (cnn)": "convolutional neural network",
    "convolutional neural networks": "convolutional neural network",
    "svm": "support vector machine",
    "ica": "independent component analysis",
    "independent component analysis (ica)": "independent component analysis",
    "meg": "magnetoencephalography",
    "neuronal networks": "neural network",
    "neural networks": "neural network",
    "artifacts": "artifact removal",
    "emotion": "emotion recognition",
    "deep learning (dl)": "deep learning",
    "explainable artificial intelligence": "explainable ai",
}

class BERTopicPipeline:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", term_mapping: Optional[Dict] = None):
        self.model_name = model_name
        self.term_mapping = term_mapping or DEFAULT_TERM_MAPPING
        self.topic_model = None

    def preprocess_keywords(self, df: pl.DataFrame, column: str = "Author Keywords") -> pl.DataFrame:
        """Standardizes and explodes keywords as per existing logic."""
        return df.with_columns(
            pl.col(column).str.split(";").alias("keyword_list")
        ).explode("keyword_list").with_columns(
            pl.col("keyword_list")
            .str.strip_chars()
            .str.to_lowercase()
            .alias("processed_keyword")
        ).filter(
            ~pl.col("processed_keyword").str.contains("(?i)eeg|electroencephalo")
        ).with_columns(
            pl.col("processed_keyword")
            .replace_strict(self.term_mapping, default=pl.col("processed_keyword"))
            .alias("standardized_word")
        )

    def fit_model(self, docs: List[str]):
        """Fits BERTopic on a list of documents (abstracts)."""
        device = "cuda" if HAS_TORCH_CUDA else "cpu"
        logging.info(f"BERTopic: Fitting model using {device} (RAPIDS accelerated: {HAS_RAPIDS_CUML})")
        
        if HAS_RAPIDS_CUML:
            # RAPIDS-accelerated pipeline
            umap_model = UMAP(n_components=5, n_neighbors=15, min_dist=0.0)
            hdbscan_model = HDBSCAN(min_cluster_size=10, prediction_data=True)
            self.topic_model = BERTopic(
                embedding_model=self.model_name, 
                umap_model=umap_model, 
                hdbscan_model=hdbscan_model,
                calculate_probabilities=True
            )
        else:
            # Standard CPU pipeline (BERTopic handles default UMAP/HDBSCAN)
            self.topic_model = BERTopic(embedding_model=self.model_name, calculate_probabilities=True)
        
        topics, probs = self.topic_model.fit_transform(docs)
        return topics, probs

    def calculate_cagr(self, df: pl.DataFrame, count_col: str = "count", year_col: str = "Year") -> pl.DataFrame:
        """Calculates Compound Annual Growth Rate for standardized terms."""
        cagr_data = df.sort(year_col).group_by("standardized_word").agg(
            first_year_count=pl.col(count_col).first(),
            last_year_count=pl.col(count_col).last(),
            first_year=pl.col(year_col).first(),
            last_year=pl.col(year_col).last()
        )
        
        cagr_data = cagr_data.with_columns(
            years_diff=(pl.col("last_year") - pl.col("first_year")).cast(pl.Float64)
        )
        
        cagr_data = cagr_data.with_columns(
            pl.when((pl.col("years_diff") > 0) & (pl.col("first_year_count") > 0))
            .then((pl.col("last_year_count") / pl.col("first_year_count")).pow(1.0 / pl.col("years_diff")) - 1)
            .otherwise(None)
            .alias("cagr")
        ).with_columns(
            (pl.col("cagr") * 100).alias("cagr_percent")
        )
        
        return cagr_data.filter(
            (pl.col("years_diff") > 0) & (pl.col("last_year_count") >= 10)
        ).sort("cagr_percent", descending=True)

    def get_topics(self):
        if self.topic_model:
            return self.topic_model.get_topic_info()
        return None

    def get_topics_over_time(self, docs: List[str], timestamps: List[int]) -> pd.DataFrame:
        """Leverages BERTopic's topics_over_time to analyze how topics evolve."""
        if not self.topic_model:
            return pd.DataFrame()
        try:
            topics_over_time = self.topic_model.topics_over_time(docs, timestamps)
            return topics_over_time
        except Exception as e:
            logging.error(f"Failed to generate topics over time: {e}")
            return pd.DataFrame()

    def get_topic_keyword_matrix(self, df: pl.DataFrame, docs_col: str, keyword_col: str = "standardized_word") -> pd.DataFrame:
        """
        Creates a correlation matrix mapping author keywords to BERTopic clusters.
        Assumes `df` is the output of `preprocess_keywords` and has a `Topic` column
        assigned from the BERTopic predictions.
        """
        if not self.topic_model or "Topic" not in df.columns:
            return pd.DataFrame()

        try:
            # We want a crosstab/pivot of Topic vs Keyword
            pandas_df = df.to_pandas()
            # Filter out outlier topic
            pandas_df = pandas_df[pandas_df["Topic"] != -1]
            if pandas_df.empty:
                return pd.DataFrame()

            # Group by Topic and Keyword, count occurrences
            matrix = pd.crosstab(pandas_df["Topic"], pandas_df[keyword_col])

            # Map topic IDs to Topic Names for better readability
            topic_info = self.topic_model.get_topic_info()
            topic_name_map = dict(zip(topic_info['Topic'], topic_info['Name']))

            matrix.index = matrix.index.map(lambda x: topic_name_map.get(x, f"Topic {x}"))
            return matrix
        except Exception as e:
            logging.error(f"Failed to generate topic-keyword correlation: {e}")
            return pd.DataFrame()

    def get_research_lines(self, nr_clusters: int = 5) -> pd.DataFrame:
        """Groups topics into broader 'Research Lines' using hierarchical clustering."""
        if not self.topic_model or len(self.topic_model.get_topic_info()) < 2:
            return pd.DataFrame()

        try:
            # Hierarchical clustering of topics
            hierarchical_topics = self.topic_model.hierarchical_topics(
                docs=self.topic_model.docs, 
                nr_clusters=nr_clusters
            )
            
            # Get basic topic info
            topic_info = self.topic_model.get_topic_info()
            
            # Map topics to their high-level research line labels
            # BERTopic provides labels for merged topics in the hierarchical tree
            research_lines = []
            for _, row in topic_info.iterrows():
                topic_id = row['Topic']
                if topic_id == -1: continue # Skip outliers
                
                # Get the top keywords for this topic
                words = [w[0] for w in self.topic_model.get_topic(topic_id)[:5]]
                
                research_lines.append({
                    "topic_id": topic_id,
                    "topic_label": row.get('Name', f"Topic {topic_id}"),
                    "keywords": ", ".join(words),
                    "count": row.get('Count', 0),
                    # We can use the hierarchical labels if we want more depth, 
                    # but for now, we'll return the refined topic list as the base for 'Research Lines'
                })
                
            return pd.DataFrame(research_lines)
        except Exception as e:
            logging.error(f"Failed to generate research lines: {e}")
            return pd.DataFrame()

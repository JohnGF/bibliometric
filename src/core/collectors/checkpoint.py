import os
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join("data", ".cache", "scraping")

class ScrapeCheckpointManager:
    """Manager for saving and restoring scraping checkpoints across paginated API requests.
    
    Prevents data loss and avoids re-fetching pages when rate limits, crashes, or network errors occur.
    """
    
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _generate_key(self, source: str, query: str, start_year: Optional[int] = None, end_year: Optional[int] = None) -> str:
        raw_key = f"{source.strip().lower()}:{query.strip().lower()}:{start_year}:{end_year}"
        hash_str = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
        clean_source = "".join(c for c in source.lower() if c.isalnum())
        return f"chk_{clean_source}_{hash_str}"
        
    def get_checkpoint_path(self, source: str, query: str, start_year: Optional[int] = None, end_year: Optional[int] = None) -> str:
        key = self._generate_key(source, query, start_year, end_year)
        return os.path.join(self.cache_dir, f"{key}.json")
        
    def load(self, source: str, query: str, start_year: Optional[int] = None, end_year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        path = self.get_checkpoint_path(source, query, start_year, end_year)
        if not os.path.exists(path):
            return None
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            received_count = len(data.get("items", []))
            received_pages = data.get("received_pages", [])
            last_page = data.get("last_page", 0)
            last_cursor = data.get("last_cursor", "*")
            offset = data.get("offset", 0)
            is_complete = data.get("is_complete", False)
            
            logger.info(
                f"[{source.upper()} CHECKPOINT FOUND] Restored {received_count} items across {len(received_pages)} pages. "
                f"Resuming from page={last_page}, offset={offset}, cursor={str(last_cursor)[:12]}... (Complete: {is_complete})"
            )
            return data
        except Exception as e:
            logger.warning(f"Failed to read checkpoint file {path}: {e}")
            return None
            
    def save(
        self,
        source: str,
        query: str,
        items: List[Dict[str, Any]],
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        page: int = 0,
        cursor: Optional[str] = "*",
        offset: int = 0,
        received_pages: Optional[List[int]] = None,
        is_complete: bool = False
    ) -> str:
        path = self.get_checkpoint_path(source, query, start_year, end_year)
        
        if received_pages is None:
            received_pages = list(range(1, page + 1)) if page > 0 else []
            
        payload = {
            "source": source,
            "query": query,
            "start_year": start_year,
            "end_year": end_year,
            "last_page": page,
            "last_cursor": cursor,
            "offset": offset,
            "received_pages": received_pages,
            "received_count": len(items),
            "is_complete": is_complete,
            "items": items
        }
        
        tmp_path = f"{path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
            logger.debug(f"[{source.upper()}] Saved checkpoint to {path} ({len(items)} items, page {page})")
        except Exception as e:
            logger.error(f"Failed to save checkpoint for {source}: {e}")
            
        return path

    def clear(self, source: str, query: str, start_year: Optional[int] = None, end_year: Optional[int] = None):
        path = self.get_checkpoint_path(source, query, start_year, end_year)
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Cleared checkpoint file {path}")
            except Exception as e:
                logger.warning(f"Failed to remove checkpoint file {path}: {e}")

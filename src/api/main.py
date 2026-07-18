from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import logging
import pandas as pd
from src.pipeline import BibliometricPipeline
from src.core.collection import UnifiedCollector

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Bibliometric Research API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state
pipeline = BibliometricPipeline(output_dir="pipeline_results")
collector = UnifiedCollector()
active_tasks = {}

# Static files for results and data
os.makedirs("pipeline_results", exist_ok=True)
app.mount("/api/results", StaticFiles(directory="pipeline_results"), name="results")
os.makedirs("data", exist_ok=True)
app.mount("/api/data", StaticFiles(directory="data"), name="data")

# --- API ROUTES ---

@app.get("/api/health")
def health_check():
    gpu_available = False
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except:
        gpu_available = os.environ.get("NVIDIA_VISIBLE_DEVICES") != "void"
    return {"status": "healthy", "gpu_available": gpu_available}

class CollectionRequest(BaseModel):
    query: str
    limit: int = 100
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    sources: Optional[List[str]] = None

@app.post("/api/collect")
async def collect_papers(request: CollectionRequest, background_tasks: BackgroundTasks):
    task_id = f"collect_{request.query.replace(' ', '_')}"
    def run_collection():
        try:
            active_tasks[task_id] = "running"
            df = collector.fetch_all(request.query, limit_per_source=request.limit, start_year=request.start_year, end_year=request.end_year, sources=request.sources)
            if df.empty:
                active_tasks[task_id] = "failed: no data found"
                return
            safe_query = request.query.replace(' ', '_').replace('/', '_')
            filename = f"data/collected_{safe_query}.csv"
            df.to_csv(filename, index=False)
            active_tasks[task_id] = f"completed: {filename}"
        except Exception as e:
            active_tasks[task_id] = f"error: {str(e)}"
    background_tasks.add_task(run_collection)
    return {"task_id": task_id, "status": "accepted"}

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    return {"task_id": task_id, "status": active_tasks.get(task_id, "not_found")}

# --- FRONTEND SERVING ---

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out"))

# Mount the static files (JS, CSS, images)
if os.path.exists(os.path.join(frontend_path, "_next")):
    app.mount("/_next", StaticFiles(directory=os.path.join(frontend_path, "_next")), name="next-static")

# Catch-all for the frontend
@app.get("/{rest_of_path:path}")
async def serve_frontend(rest_of_path: str):
    # Skip API calls
    if rest_of_path.startswith("api/"):
        raise HTTPException(status_code=404)
        
    # Check if the file exists directly (e.g. favicon.ico, images)
    file_path = os.path.join(frontend_path, rest_of_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
        
    # Otherwise serve index.html (Next.js client-side routing)
    return FileResponse(os.path.join(frontend_path, "index.html"))


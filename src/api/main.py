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

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

@app.get("/api/list-folders")
def list_folders():
    """Lists directories in the workspace containing CSV, Parquet, or output files."""
    folders = []
    for item in os.listdir(WORKSPACE_ROOT):
        full_p = os.path.join(WORKSPACE_ROOT, item)
        if os.path.isdir(full_p) and not item.startswith(".") and item not in ["frontend", "src", "node_modules", ".venv", "__pycache__"]:
            # Check if directory has data or result files
            files = os.listdir(full_p)
            if any(f.endswith((".csv", ".parquet", ".pdf", ".png")) for f in files):
                folders.append(item)
    return {"folders": sorted(folders)}

@app.get("/api/list-data")
def list_data():
    files = [f for f in os.listdir("data") if os.path.isfile(os.path.join("data", f))] if os.path.exists("data") else []
    return {"data": files}

@app.get("/api/list-results")
def list_results():
    files = [f for f in os.listdir("pipeline_results") if os.path.isfile(os.path.join("pipeline_results", f))] if os.path.exists("pipeline_results") else []
    return {"results": files}

@app.get("/api/list-files/{folder_path:path}")
def list_files_in_folder(folder_path: str):
    target_dir = os.path.abspath(os.path.join(WORKSPACE_ROOT, folder_path))
    if not target_dir.startswith(WORKSPACE_ROOT) or not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail="Folder not found")
    
    files = [f for f in os.listdir(target_dir) if os.path.isfile(os.path.join(target_dir, f))]
    return {"folder": folder_path, "files": sorted(files)}

@app.get("/api/dataset-preview-path")
def preview_dataset_path(path: str):
    file_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, path))
    if not file_path.startswith(WORKSPACE_ROOT) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    
    try:
        filename = os.path.basename(file_path)
        if filename.endswith(".csv"):
            df = pd.read_csv(file_path, nrows=2000)
        elif filename.endswith(".parquet"):
            df = pd.read_parquet(file_path)
            df = df.head(2000)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
            
        df = df.fillna("")
        columns = df.columns.tolist()
        rows = df.to_dict(orient="records")
        return {"columns": columns, "rows": rows, "total_rows": len(df), "filename": filename, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse dataset: {str(e)}")

@app.get("/api/dataset-preview/{folder}/{filename}")
def preview_dataset(folder: str, filename: str):
    rel_path = os.path.join(folder, filename)
    return preview_dataset_path(rel_path)

@app.get("/api/file/{file_path:path}")
def get_workspace_file(file_path: str):
    abs_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, file_path))
    if not abs_path.startswith(WORKSPACE_ROOT) or not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path)

# --- FRONTEND SERVING ---

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out"))

# Mount static Next.js assets for both root and /biblio routes
if os.path.exists(os.path.join(frontend_path, "_next")):
    next_dir = os.path.join(frontend_path, "_next")
    app.mount("/_next", StaticFiles(directory=next_dir), name="next-static")
    app.mount("/biblio/_next", StaticFiles(directory=next_dir), name="next-static-biblio")

# Catch-all for the frontend
@app.get("/{rest_of_path:path}")
async def serve_frontend(rest_of_path: str):
    # Skip API calls
    if rest_of_path.startswith("api/"):
        raise HTTPException(status_code=404)
        
    # Normalize path by stripping optional 'biblio/' prefix
    clean_path = rest_of_path
    if clean_path.startswith("biblio/"):
        clean_path = clean_path[len("biblio/"):]
    elif clean_path == "biblio":
        clean_path = ""

    # Check direct file existence
    file_path = os.path.join(frontend_path, clean_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    file_path_orig = os.path.join(frontend_path, rest_of_path)
    if os.path.isfile(file_path_orig):
        return FileResponse(file_path_orig)

    # Return 404 for missing static assets instead of falling back to index.html
    ext = os.path.splitext(clean_path)[1].lower()
    if ext in [".js", ".css", ".map", ".json", ".ico", ".png", ".jpg", ".jpeg", ".svg", ".woff", ".woff2", ".ttf"] or clean_path.startswith("_next/"):
        raise HTTPException(status_code=404, detail="File not found")

    # Serve index.html for Next.js client-side routing
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend build not found")



# Web Dashboard & Interactive Visualization

[Back to Wiki Home](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Home.md)

---

## Overview

The web suite combines a **FastAPI backend** ([src/api/main.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/api/main.py)) and a modern **Next.js (React) frontend** ([frontend/](file:///run/media/john/ssd%20external%20storage/git/bibliometric/frontend/)).

---

## 1. FastAPI Backend API (`http://localhost:8000`)

Endpoint | Method | Description
--- | --- | ---
`/health` | `GET` | Health check reporting backend status and GPU availability.
`/collect` | `POST` | Triggers background collection across OpenAlex, Semantic Scholar, etc.
`/run` | `POST` | Executes full analysis pipeline on uploaded or collected CSV dataset.
`/status/{task_id}` | `GET` | Returns task progress and execution logs.
`/results/{filename}` | `GET` | Serves output CSVs, PDFs, and network nodes/edges.

---

## 2. Next.js Dashboard (`http://localhost:3000`)

The web UI provides:
- **Search & Collect Panel**: Live query builder with year filters and limit sliders.
- **CSV Drag-and-Drop Uploader**: Upload custom bibliometric datasets.
- **Results Dashboard**: Displays CAGR tables, country evolution charts, and research lines.

---

## 3. Interactive `NetworkVisualizer.tsx`

Located at [frontend/src/app/NetworkVisualizer.tsx](file:///run/media/john/ssd%20external%20storage/git/bibliometric/frontend/src/app/NetworkVisualizer.tsx).

### Features & Control Knobs
- **Live 60fps Physics Simulation**: Interactive force-directed physics with draggable nodes.
- **Leaders Per Group Slider**: Dynamically isolate top 1, 2, 3, or 5 leaders per Louvain community partition.
- **Min Citations & Min Publications**: Filter out low-impact authors in real-time.
- **Node Diameter Scaling**: Scale nodes by Publications, Citations, or PageRank influence.
- **Search & Recenter**: Instant author search with highlight connections and central gravity.

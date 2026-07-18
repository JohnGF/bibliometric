"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, Play, FileText, CheckCircle, AlertCircle, Loader2, Download, Database, BarChart3, Network, Sliders, UploadCloud, RefreshCw, RotateCcw, Target, Layers } from "lucide-react";
import NetworkVisualizer from "./NetworkVisualizer";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Dashboard() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(100);
  const [status, setStatus] = useState("Ready");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [results, setResults] = useState<string[]>([]);
  const [dataFiles, setDataFiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<{status: string, gpu_available: boolean} | null>(null);
  const [showVisualizer, setShowVisualizer] = useState(false);
  const [cagrData, setCagrData] = useState<any[]>([]);
  const [countryData, setCountryData] = useState<any[]>([]);
  const [researchLines, setResearchLines] = useState<any[]>([]);

  // Global Config Variables
  const [theme, setTheme] = useState("whitegrid");
  const [minPublications, setMinPublications] = useState(1);
  const [topNCountries, setTopNCountries] = useState(10);
  const [startYear, setStartYear] = useState("");
  const [endYear, setEndYear] = useState("");

  // File Upload drag-and-drop states
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasNetworkData = results.includes("network_nodes.csv") && results.includes("network_edges.csv");

  const [timeStr, setTimeStr] = useState("");

  // Check backend health
  useEffect(() => {
    setTimeStr(new Date().toLocaleTimeString());

    fetch(`${API_BASE}/health`)
      .then(res => res.json())
      .then(data => setHealth(data))
      .catch(() => setHealth({status: "offline", gpu_available: false}));
    
    refreshAll();
  }, []);

  // Poll task status if active
  useEffect(() => {
    if (!taskId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/tasks/${taskId}`);
        const data = await res.json();
        setStatus(data.status);
        
        if (data.status.startsWith("completed") || data.status.startsWith("error") || data.status.startsWith("failed")) {
          setTaskId(null);
          refreshAll();
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [taskId]);

  const refreshAll = () => {
    refreshResults();
    refreshDataFiles();
    fetchInsights();
  };

  const fetchInsights = async () => {
    try {
      const [cagrRes, countryRes, researchRes] = await Promise.all([
        fetch(`${API_BASE}/results/keywords-cagr`).catch(() => null),
        fetch(`${API_BASE}/results/country-evolution`).catch(() => null),
        fetch(`${API_BASE}/results/research-lines`).catch(() => null)
      ]);

      if (cagrRes && cagrRes.ok) {
        const data = await cagrRes.json();
        setCagrData(data.slice(0, 15)); // Top 15 keywords
      } else {
        setCagrData([]);
      }

      if (countryRes && countryRes.ok) {
        const data = await countryRes.json();
        setCountryData(data);
      } else {
        setCountryData([]);
      }

      if (researchRes && researchRes.ok) {
        const data = await researchRes.json();
        setResearchLines(data);
      } else {
        setResearchLines([]);
      }
    } catch (err) {
      console.error("Failed to fetch insights:", err);
    }
  };

  const refreshResults = async () => {
    try {
      const res = await fetch(`${API_BASE}/list-results`);
      const data = await res.json();
      setResults(data.results);
    } catch (err) {
      console.error("Failed to fetch results:", err);
    }
  };

  const refreshDataFiles = async () => {
    try {
      const res = await fetch(`${API_BASE}/list-data`);
      const data = await res.json();
      setDataFiles(data.data);
    } catch (err) {
      console.error("Failed to fetch data files:", err);
    }
  };

  const handleCollect = async () => {
    if (!query) return;
    setLoading(true);
    setStatus("Initiating collection...");
    try {
      const payload: any = { query, limit };
      if (startYear) payload.start_year = parseInt(startYear);
      if (endYear) payload.end_year = parseInt(endYear);

      const res = await fetch(`${API_BASE}/collect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      setTaskId(data.task_id);
    } catch (err) {
      setStatus("Collection failed");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (fileName: string) => {
    setLoading(true);
    setStatus(`Analyzing ${fileName}...`);
    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          file_path: `data/${fileName}`,
          config: {
            theme,
            min_publications: minPublications,
            top_n_countries: topNCountries
          }
        })
      });
      const data = await res.json();
      setTaskId(data.task_id);
    } catch (err) {
      setStatus("Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await handleFileUpload(e.target.files[0]);
    }
  };

  const onButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!ext || !["csv", "parquet", "xlsx", "xls"].includes(ext)) {
      setStatus("Error: Unsupported file format. Please upload CSV, Parquet, or Excel files.");
      return;
    }

    setLoading(true);
    setStatus(`Uploading ${file.name}...`);
    
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const data = await res.json();
      setStatus(`Uploaded successfully: ${data.filename}`);
      refreshAll();
    } catch (err: any) {
      console.error(err);
      setStatus(`Upload failed: ${err.message || err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResetConfig = () => {
    setTheme("whitegrid");
    setMinPublications(1);
    setTopNCountries(10);
    setStartYear("");
    setEndYear("");
    setLimit(100);
    setQuery("");
    setStatus("Ready");
    setTaskId(null);
  };

  const handleClearConsole = () => {
    setStatus("Ready");
    setTaskId(null);
    setQuery("");
  };

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <header className="mb-12 flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-slate-900 mb-2 tracking-tight">Bibliometric Autopilot</h1>
          <p className="text-slate-500 italic">FastAPI + Next.js Research Dashboard</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${health?.status === "healthy" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
            API: {health?.status || "Checking..." }
          </span>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${health?.gpu_available ? "bg-blue-100 text-blue-700" : "bg-orange-100 text-orange-700"}`}>
            GPU: {health?.gpu_available ? "Enabled" : "CPU Fallback"}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          {/* Global Variable Configuration */}
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold flex items-center gap-2 text-slate-800">
                <Sliders className="w-5 h-5 text-indigo-600" />
                Global Configuration Options
              </h2>
              <button 
                onClick={handleResetConfig}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg transition-all"
                title="Reset local state to defaults"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Options
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 border-t border-slate-100 pt-6">
              {/* Column 1: Extraction Settings */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-slate-900 border-b pb-2 flex items-center gap-2">
                  <Database className="w-4 h-4 text-blue-500" />
                  Data Extraction Settings
                </h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 mb-1.5">Start Year</label>
                    <input 
                      type="number" 
                      placeholder="e.g. 2020" 
                      value={startYear} 
                      onChange={(e) => setStartYear(e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm text-slate-700 bg-slate-50/50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 mb-1.5">End Year</label>
                    <input 
                      type="number" 
                      placeholder="e.g. 2025" 
                      value={endYear} 
                      onChange={(e) => setEndYear(e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm text-slate-700 bg-slate-50/50"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-xs font-semibold text-slate-500 mb-1.5">API Source Fetch Limit</label>
                  <input 
                    type="number" 
                    min={1}
                    value={limit}
                    onChange={(e) => setLimit(Math.max(1, parseInt(e.target.value) || 1))}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm text-slate-700 bg-slate-50/50"
                    placeholder="e.g. 1000"
                  />
                  <p className="text-[10px] text-slate-400 mt-1.5 leading-relaxed">
                    * Recommended safe range: 50–500 papers. To analyze large datasets (e.g., 33,000+), please upload your own CSV/Parquet file directly using the Dropzone below to bypass API rate-limiting.
                  </p>
                </div>
              </div>
              
              {/* Column 2: Analysis Settings */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-slate-900 border-b pb-2 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-purple-500" />
                  Pipeline Analysis Settings
                </h3>
                
                <div>
                  <label className="block text-xs font-semibold text-slate-500 mb-1.5">Matplotlib PDF Theme</label>
                  <select 
                    value={theme} 
                    onChange={(e) => setTheme(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg bg-slate-50/50 focus:ring-2 focus:ring-indigo-500 outline-none text-sm text-slate-700"
                  >
                    <option value="whitegrid">White Grid Theme</option>
                    <option value="darkgrid">Dark Grid Theme</option>
                    <option value="ticks">Ticks Accent Theme</option>
                    <option value="white">Minimal White Theme</option>
                  </select>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 mb-1.5">Min Publications</label>
                    <input 
                      type="number" 
                      min={1} 
                      value={minPublications} 
                      onChange={(e) => setMinPublications(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm text-slate-700 bg-slate-50/50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 mb-1.5">Top Countries Traced</label>
                    <input 
                      type="number" 
                      min={1} 
                      value={topNCountries} 
                      onChange={(e) => setTopNCountries(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm text-slate-700 bg-slate-50/50"
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Step 1: Collection */}
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
              <Search className="w-5 h-5 text-blue-500" />
              1. Search & Collect
            </h2>
            <div className="space-y-4">
              <div className="flex gap-4">
                <input
                  type="text"
                  placeholder="Query (e.g. brain-computer interface)"
                  className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <input 
                  type="number"
                  min={1}
                  value={limit}
                  onChange={(e) => setLimit(Math.max(1, parseInt(e.target.value) || 1))}
                  className="px-4 py-2 border rounded-lg outline-none bg-slate-50 focus:ring-2 focus:ring-blue-500 text-slate-700 w-32"
                  placeholder="Limit"
                  title="Limit per source"
                />
              </div>
              <button 
                onClick={handleCollect}
                disabled={loading || !!taskId}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-xl transition-all disabled:opacity-50 flex justify-center items-center gap-2 shadow-lg shadow-blue-200"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                Fetch Data from APIs
              </button>
            </div>
          </section>

          {/* Step 2: Analysis & Upload */}
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Database className="w-5 h-5 text-purple-500" />
                2. Upload & Analyze Datasets
              </h2>
              <button 
                onClick={refreshAll}
                className="text-xs font-semibold text-purple-600 hover:text-purple-800 flex items-center gap-1 bg-purple-50 hover:bg-purple-100 px-3 py-1.5 rounded-lg transition-all"
                title="Refresh datasets directory"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Refresh Datasets
              </button>
            </div>

            <div className="space-y-6">
              {/* Drag & Drop File Uploader */}
              <div 
                onDragEnter={handleDrag} 
                onDragOver={handleDrag} 
                onDragLeave={handleDrag} 
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
                  dragActive ? "border-indigo-500 bg-indigo-50/50 animate-pulse" : "border-slate-300 hover:border-indigo-400 bg-slate-50"
                }`}
              >
                <UploadCloud className="w-10 h-10 mx-auto text-indigo-500 mb-3" />
                <p className="text-sm font-semibold text-slate-700">Drag & Drop your own dataset here</p>
                <p className="text-xs text-slate-500 mt-1">Supports CSV, Parquet, or Excel files (.csv, .parquet, .xlsx)</p>
                <div className="mt-4">
                  <button 
                    type="button" 
                    onClick={onButtonClick}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2.5 rounded-lg transition-colors shadow-md shadow-indigo-200"
                  >
                    Select File
                  </button>
                  <input 
                    ref={fileInputRef}
                    type="file" 
                    accept=".csv,.parquet,.xlsx,.xls" 
                    onChange={handleFileChange} 
                    className="hidden" 
                  />
                </div>
              </div>

              <div className="border-t border-slate-100 pt-6">
                <h3 className="text-sm font-bold text-slate-800 mb-4 uppercase tracking-wider">Available Local Datasets</h3>
                {dataFiles.length === 0 ? (
                  <div className="text-center py-8 border-2 border-dashed rounded-xl text-slate-400">
                    No data files found. Collect or upload some data first!
                  </div>
                ) : (
                  <div className="grid gap-3">
                    {dataFiles.map((file) => (
                      <div key={file} className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-blue-200 transition-colors">
                        <div className="flex items-center gap-3">
                          <FileText className="w-5 h-5 text-slate-400" />
                          <div>
                            <p className="font-medium text-slate-800 text-sm">{file}</p>
                            <p className="text-xs text-slate-500">Ready for Bibliometric Pipeline</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <a 
                            href={`${API_BASE}/data/${file}`} 
                            target="_blank"
                            className="p-2 text-slate-400 hover:text-blue-600 transition-colors"
                            title="Download CSV"
                          >
                            <Download className="w-5 h-5" />
                          </a>
                          <button 
                            onClick={() => handleAnalyze(file)}
                            disabled={loading || !!taskId}
                            className="bg-slate-900 hover:bg-slate-800 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
                          >
                            <BarChart3 className="w-4 h-4" />
                            Run Analysis
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-4 p-4 bg-blue-50 rounded-xl border border-blue-100">
                <h4 className="text-sm font-bold text-blue-900 mb-1 italic">Expected CSV Schema:</h4>
                <p className="text-xs text-blue-800">
                  Title, Abstract, Authors, Year, Affiliations, DOI, Cite Count
                </p>
              </div>
            </div>
          </section>

          {/* Step 3: Bibliometric Insights */}
          {(cagrData.length > 0 || countryData.length > 0 || researchLines.length > 0) && (
            <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-8">
              <h2 className="text-xl font-semibold flex items-center gap-2 text-slate-800">
                <BarChart3 className="w-5 h-5 text-emerald-500" />
                3. Bibliometric Insights & Trends
              </h2>

              <div className="grid grid-cols-1 gap-12">
                {/* Research Lines Section */}
                {researchLines.length > 0 && (
                  <div className="space-y-6">
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2 border-b pb-2">
                      <Target className="w-4 h-4 text-rose-500" />
                      Identified Research Lines (Thematic Clusters)
                    </h3>
                    <div className="grid gap-4">
                      {researchLines.map((line: any, idx: number) => (
                        <div key={idx} className="bg-slate-50 border border-slate-100 rounded-xl p-4 hover:border-rose-200 transition-all group">
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center gap-2">
                              <Layers className="w-4 h-4 text-rose-400" />
                              <span className="font-bold text-slate-800 text-sm truncate max-w-[300px] capitalize">
                                {line.topic_label.replace(/^\d+_/, "").replace(/_/g, " ")}
                              </span>
                            </div>
                            <span className="bg-rose-100 text-rose-700 text-[10px] font-bold px-2 py-0.5 rounded-full">
                              {line.count} Papers
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 italic mb-2 leading-relaxed">
                            "{line.keywords}"
                          </p>
                          <div className="w-full bg-slate-200 rounded-full h-1 mt-3 overflow-hidden">
                            <div 
                              className="bg-rose-500 h-full rounded-full group-hover:bg-rose-600 transition-all duration-700"
                              style={{ width: `${Math.min(100, (line.count / Math.max(...researchLines.map((l: any) => l.count))) * 100)}%` }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* CAGR Chart */}
                {cagrData.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2 border-b pb-2">
                      <RotateCcw className="w-4 h-4 text-indigo-500" />
                      Keyword Growth Trends (CAGR %)
                    </h3>
                    <div className="space-y-3">
                      {cagrData.map((item, idx) => {
                        const val = parseFloat(item.cagr_percent);
                        const width = Math.min(Math.max(val, 5), 100);
                        return (
                          <div key={idx} className="space-y-1">
                            <div className="flex justify-between text-xs font-medium">
                              <span className="text-slate-700 capitalize">{item.standardized_word}</span>
                              <span className="text-emerald-600">+{val.toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                              <div 
                                className="bg-gradient-to-r from-emerald-400 to-teal-500 h-full rounded-full transition-all duration-1000"
                                style={{ width: `${width}%` }}
                              ></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Country Evolution */}
                {countryData.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2 border-b pb-2">
                      <Database className="w-4 h-4 text-orange-500" />
                      Top Country Scientific Output
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {countryData.slice(0, 9).map((item, idx) => (
                        <div key={idx} className="bg-slate-50 border border-slate-100 rounded-xl p-3 flex flex-col items-center justify-center text-center">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tighter mb-1">{item.Country}</span>
                          <span className="text-xl font-bold text-slate-800">{item.Count}</span>
                          <span className="text-[10px] text-slate-500">Publications</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>

        {/* Status Panel */}
        <div className="space-y-8">
          <section className="bg-slate-900 text-white rounded-2xl shadow-xl p-6 h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-400" />
                System Status
              </h2>
              <button 
                onClick={handleClearConsole}
                className="text-xs font-semibold text-slate-400 hover:text-white flex items-center gap-1 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg transition-all border border-slate-750"
                title="Clear local logs and query"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Log
              </button>
            </div>
            
            <div className="bg-slate-800 rounded-xl p-4 mb-6 font-mono text-sm min-h-[120px] border border-slate-700">
              <div className="text-slate-500 mb-2"># {timeStr}</div>
              <div className={status.includes("error") || status.includes("failed") ? "text-red-400" : "text-green-400"}>
                {status}
              </div>
              {taskId && (
                <div className="mt-4 flex items-center gap-2 text-slate-400 text-xs">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Task ID: {taskId}
                </div>
              )}
            </div>
            
            <div className="flex-1 space-y-6">
              <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider flex justify-between items-center">
                Generated Results
                <button 
                  onClick={refreshAll} 
                  className="hover:text-white text-slate-500 p-1 hover:bg-slate-800 rounded transition-all"
                  title="Refresh Generated Results"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </h3>

              {hasNetworkData && (
                <button
                  onClick={() => setShowVisualizer(true)}
                  className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium py-3 rounded-xl transition-all shadow-lg shadow-indigo-950/30 flex justify-center items-center gap-2 border border-blue-500/10 text-xs tracking-wider uppercase"
                >
                  <Network className="w-4 h-4 animate-pulse" />
                  Visualize GPU Network
                </button>
              )}

              <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                {results.length === 0 ? (
                  <div className="text-slate-600 italic text-sm py-4 border border-dashed border-slate-700 rounded-xl text-center">
                    No outputs yet.
                  </div>
                ) : (
                  results.map((file, i) => (
                    <div key={i} className="flex items-center justify-between bg-slate-800/50 p-3 rounded-xl group border border-transparent hover:border-slate-600 transition-all">
                      <div className="flex flex-col">
                        <span className="text-xs text-slate-300 truncate max-w-[160px] font-medium">{file}</span>
                        <span className="text-[10px] text-slate-500">{file.endsWith('.csv') ? 'Dataset' : 'Visualization'}</span>
                      </div>
                      <a 
                        href={`${API_BASE}/results/${file}`} 
                        target="_blank"
                        className="p-2 bg-slate-700 group-hover:bg-blue-600 rounded-lg text-slate-400 group-hover:text-white transition-all shadow-sm"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>
        </div>
      </div>

      {showVisualizer && (
        <NetworkVisualizer apiBase={API_BASE} onClose={() => setShowVisualizer(false)} />
      )}
    </main>
  );
}

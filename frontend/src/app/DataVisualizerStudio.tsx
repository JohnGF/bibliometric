"use client";

import React, { useState, useEffect, useMemo } from "react";
import { 
  BarChart3, LineChart, PieChart, ScatterChart, AreaChart, 
  X, RefreshCw, Download, Sliders, Palette, Filter, 
  ArrowUpDown, Table, Sparkles, Check, ChevronDown, Layers, Folder
} from "lucide-react";

interface DataVisualizerStudioProps {
  apiBase: string;
  onClose: () => void;
  initialFile?: string;
  initialFolder?: string;
}

type ChartType = "bar" | "hbar" | "line" | "area" | "pie" | "scatter";
type PaletteType = "indigo" | "emerald" | "rose" | "ocean" | "midnight";

const COLOR_PALETTES: Record<PaletteType, { primary: string; secondary: string; gradient: string[]; text: string; bg: string }> = {
  indigo: {
    primary: "#6366f1",
    secondary: "#a855f7",
    gradient: ["#6366f1", "#818cf8", "#a855f7", "#c084fc", "#e879f9", "#38bdf8"],
    text: "text-indigo-600",
    bg: "bg-indigo-50 border-indigo-200"
  },
  emerald: {
    primary: "#10b981",
    secondary: "#14b8a6",
    gradient: ["#10b981", "#34d399", "#14b8a6", "#2dd4bf", "#06b6d4", "#38bdf8"],
    text: "text-emerald-600",
    bg: "bg-emerald-50 border-emerald-200"
  },
  rose: {
    primary: "#f43f5e",
    secondary: "#fb7185",
    gradient: ["#f43f5e", "#fb7185", "#f97316", "#fb923c", "#eab308", "#ec4899"],
    text: "text-rose-600",
    bg: "bg-rose-50 border-rose-200"
  },
  ocean: {
    primary: "#0284c7",
    secondary: "#2563eb",
    gradient: ["#0284c7", "#38bdf8", "#2563eb", "#60a5fa", "#0d9488", "#2dd4bf"],
    text: "text-sky-600",
    bg: "bg-sky-50 border-sky-200"
  },
  midnight: {
    primary: "#3b82f6",
    secondary: "#8b5cf6",
    gradient: ["#3b82f6", "#60a5fa", "#8b5cf6", "#a78bfa", "#ec4899", "#f43f5e"],
    text: "text-blue-400",
    bg: "bg-slate-800 border-slate-700"
  }
};

export default function DataVisualizerStudio({ apiBase, onClose, initialFile, initialFolder }: DataVisualizerStudioProps) {
  const [folders, setFolders] = useState<string[]>(["data", "pipeline_results", "pipeline_results_original_33k"]);
  const [selectedFolder, setSelectedFolder] = useState<string>(initialFolder || "pipeline_results_original_33k");
  const [availableFiles, setAvailableFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>(initialFile || "");
  
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Raw dataset parsed
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, any>[]>([]);

  // Controls state
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [xAxisCol, setXAxisCol] = useState<string>("");
  const [metricCol, setMetricCol] = useState<string>("__count__");
  const [aggregation, setAggregation] = useState<"count" | "sum" | "avg" | "max" | "min">("count");
  const [palette, setPalette] = useState<PaletteType>("indigo");
  const [topN, setTopN] = useState<number>(15);
  const [sortOrder, setSortOrder] = useState<"desc" | "asc" | "natural">("desc");
  const [activeTab, setActiveTab] = useState<"chart" | "table">("chart");

  // Load list of folders from backend
  useEffect(() => {
    fetch(`${apiBase}/api/list-folders`)
      .then(res => res.json())
      .then(data => {
        if (data.folders && data.folders.length > 0) {
          setFolders(data.folders);
          if (!data.folders.includes(selectedFolder)) {
            setSelectedFolder(data.folders[0]);
          }
        }
      })
      .catch(() => {
        // Fallback default folders
        setFolders(["data", "pipeline_results", "pipeline_results_original_33k"]);
      });
  }, [apiBase]);

  // Load files in selected folder
  useEffect(() => {
    if (!selectedFolder) return;

    fetch(`${apiBase}/api/list-files/${encodeURIComponent(selectedFolder)}`)
      .then(res => res.json())
      .then(data => {
        const csvFiles = (data.files || []).filter((f: string) => f.endsWith(".csv") || f.endsWith(".parquet"));
        setAvailableFiles(csvFiles);

        if (csvFiles.length > 0 && (!selectedFile || !csvFiles.includes(selectedFile))) {
          setSelectedFile(csvFiles[0]);
        }
      })
      .catch(err => {
        console.error("Failed to list folder files:", err);
      });
  }, [selectedFolder, apiBase]);

  // Load dataset content whenever selected file or folder changes
  useEffect(() => {
    if (!selectedFile || !selectedFolder) return;

    const loadDataset = async () => {
      setLoading(true);
      setError(null);
      const fullPath = `${selectedFolder}/${selectedFile}`;

      try {
        const res = await fetch(`${apiBase}/api/dataset-preview-path?path=${encodeURIComponent(fullPath)}`);
        if (!res.ok) {
          throw new Error(`Could not load dataset at ${fullPath}`);
        }

        const data = await res.json();
        const cols: string[] = data.columns || [];
        const dataRows: Record<string, any>[] = data.rows || [];
        
        setColumns(cols);
        setRows(dataRows);

        // Smart preset detection based on filename & columns
        const fname = selectedFile.toLowerCase();
        
        if (fname.includes("yearly_growth")) {
          setXAxisCol(cols.find(c => c.toLowerCase() === "year") || cols[0]);
          setMetricCol(cols.find(c => c.toLowerCase() === "len") || "__count__");
          setAggregation("sum");
          setChartType("bar");
          setSortOrder("natural");
        } else if (fname.includes("keywords_cagr")) {
          setXAxisCol(cols.find(c => c.toLowerCase().includes("word") || c.toLowerCase().includes("keyword")) || cols[0]);
          setMetricCol(cols.find(c => c.toLowerCase().includes("cagr")) || "__count__");
          setAggregation("sum");
          setChartType("hbar");
          setSortOrder("desc");
        } else if (fname.includes("country")) {
          setXAxisCol(cols.find(c => c.toLowerCase().includes("country")) || cols[0]);
          setMetricCol(cols.find(c => c.toLowerCase().includes("count") || c.toLowerCase().includes("len")) || "__count__");
          setAggregation("sum");
          setChartType("bar");
          setSortOrder("desc");
        } else if (fname.includes("topic") || fname.includes("research_lines")) {
          setXAxisCol(cols.find(c => c.toLowerCase().includes("label") || c.toLowerCase().includes("topic")) || cols[0]);
          setMetricCol(cols.find(c => c.toLowerCase().includes("count") || c.toLowerCase().includes("len")) || "__count__");
          setAggregation("sum");
          setChartType("hbar");
          setSortOrder("desc");
        } else {
          // General fallback
          const yearCol = cols.find(c => c.toLowerCase().includes("year"));
          const categoryCol = cols.find(c => c.toLowerCase().includes("author") || c.toLowerCase().includes("country") || c.toLowerCase().includes("title"));
          setXAxisCol(yearCol || categoryCol || cols[0]);
          
          const citeCol = cols.find(c => c.toLowerCase().includes("cite") || c.toLowerCase().includes("count"));
          setMetricCol(citeCol || "__count__");
          setAggregation(citeCol ? "sum" : "count");
        }

      } catch (err: any) {
        setError(err.message || "Failed to load dataset.");
      } finally {
        setLoading(false);
      }
    };

    loadDataset();
  }, [selectedFile, selectedFolder, apiBase]);

  // Identify numeric columns
  const numericColumns = useMemo(() => {
    if (rows.length === 0) return [];
    return columns.filter(col => {
      const sample = rows.find(r => r[col] !== undefined && r[col] !== null && r[col] !== "");
      return sample && typeof sample[col] === "number";
    });
  }, [columns, rows]);

  // Aggregated data calculation for charts
  const chartData = useMemo(() => {
    if (!xAxisCol || rows.length === 0) return [];

    const map = new Map<string, { label: string; values: number[]; count: number }>();

    rows.forEach(r => {
      let rawKey = r[xAxisCol];
      if (rawKey === undefined || rawKey === null || rawKey === "") rawKey = "Unspecified";
      const key = String(rawKey);

      if (!map.has(key)) {
        map.set(key, { label: key, values: [], count: 0 });
      }
      const entry = map.get(key)!;
      entry.count += 1;

      if (metricCol !== "__count__" && typeof r[metricCol] === "number") {
        entry.values.push(r[metricCol]);
      }
    });

    let result = Array.from(map.values()).map(item => {
      let val = item.count;
      if (metricCol !== "__count__") {
        if (item.values.length === 0) {
          val = 0;
        } else if (aggregation === "sum") {
          val = item.values.reduce((a, b) => a + b, 0);
        } else if (aggregation === "avg") {
          val = item.values.reduce((a, b) => a + b, 0) / item.values.length;
        } else if (aggregation === "max") {
          val = Math.max(...item.values);
        } else if (aggregation === "min") {
          val = Math.min(...item.values);
        }
      }
      return {
        label: item.label,
        value: Math.round(val * 100) / 100,
        count: item.count
      };
    });

    // Sort order
    if (sortOrder === "desc") {
      result.sort((a, b) => b.value - a.value);
    } else if (sortOrder === "asc") {
      result.sort((a, b) => a.value - b.value);
    } else {
      // Natural / Chronological sort if numerical labels
      result.sort((a, b) => {
        const numA = Number(a.label);
        const numB = Number(b.label);
        if (!isNaN(numA) && !isNaN(numB)) return numA - numB;
        return a.label.localeCompare(b.label);
      });
    }

    if (topN > 0 && result.length > topN) {
      result = result.slice(0, topN);
    }

    return result;
  }, [rows, xAxisCol, metricCol, aggregation, sortOrder, topN]);

  // Max value for scaling
  const maxValue = useMemo(() => {
    if (chartData.length === 0) return 1;
    return Math.max(...chartData.map(d => d.value), 1);
  }, [chartData]);

  const activePalette = COLOR_PALETTES[palette];

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <div className="bg-white dark:bg-slate-900 w-full max-w-6xl rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[94vh] overflow-hidden">
        
        {/* Header Bar */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-200 dark:shadow-indigo-950/50">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                Data Visualizer Studio
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                  Folder & Path Editor
                </span>
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Load and customize charts from any result folder (e.g. pipeline_results_original_33k)
              </p>
            </div>
          </div>

          {/* Folder & Dataset Pickers */}
          <div className="flex flex-wrap items-center gap-2">
            
            {/* Folder Select */}
            <div className="flex items-center gap-1 bg-white dark:bg-slate-800 px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold">
              <Folder className="w-3.5 h-3.5 text-indigo-500" />
              <select
                value={selectedFolder}
                onChange={(e) => setSelectedFolder(e.target.value)}
                className="bg-transparent outline-none text-slate-800 dark:text-slate-200 cursor-pointer font-bold"
              >
                {folders.map((f, i) => (
                  <option key={i} value={f}>{f}</option>
                ))}
              </select>
            </div>

            {/* File Select */}
            <div className="flex items-center gap-1 bg-white dark:bg-slate-800 px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold">
              <BarChart3 className="w-3.5 h-3.5 text-purple-500" />
              <select
                value={selectedFile}
                onChange={(e) => setSelectedFile(e.target.value)}
                className="bg-transparent outline-none text-slate-800 dark:text-slate-200 cursor-pointer font-bold max-w-[220px]"
              >
                {availableFiles.length === 0 && <option value="">No CSV files</option>}
                {availableFiles.map((f, i) => (
                  <option key={i} value={f}>{f}</option>
                ))}
              </select>
            </div>

            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
              title="Close Visualizer Studio"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Main Content Layout */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 overflow-hidden">
          
          {/* Controls Sidebar */}
          <div className="p-5 border-r border-slate-200 dark:border-slate-800 space-y-6 overflow-y-auto bg-slate-50/30 dark:bg-slate-900/30">
            
            {/* Chart Type Selection */}
            <div>
              <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2.5">
                1. Chart Type
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { type: "bar", label: "Vertical Bar", icon: BarChart3 },
                  { type: "hbar", label: "Horiz Bar", icon: BarChart3 },
                  { type: "line", label: "Trend Line", icon: LineChart },
                  { type: "area", label: "Area Fill", icon: AreaChart },
                  { type: "pie", label: "Pie / Donut", icon: PieChart },
                  { type: "scatter", label: "Scatter", icon: ScatterChart },
                ].map((item) => {
                  const Icon = item.icon;
                  const active = chartType === item.type;
                  return (
                    <button
                      key={item.type}
                      onClick={() => setChartType(item.type as ChartType)}
                      className={`p-2.5 rounded-xl text-xs font-semibold flex flex-col items-center gap-1.5 border transition-all ${
                        active 
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-200 dark:shadow-none" 
                          : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-indigo-300"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span className="text-[10px]">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* X-Axis Dimension */}
            <div>
              <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2">
                2. Category / Dimension (X-Axis)
              </label>
              <select
                value={xAxisCol}
                onChange={(e) => setXAxisCol(e.target.value)}
                className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-medium text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {columns.map((col, idx) => (
                  <option key={idx} value={col}>{col}</option>
                ))}
              </select>
            </div>

            {/* Y-Axis Metric */}
            <div>
              <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2">
                3. Metric & Value (Y-Axis)
              </label>
              <div className="space-y-2">
                <select
                  value={metricCol}
                  onChange={(e) => setMetricCol(e.target.value)}
                  className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-medium text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="__count__">Count of Records (Frequency)</option>
                  {numericColumns.map((col, idx) => (
                    <option key={idx} value={col}>{col} (Numeric Value)</option>
                  ))}
                </select>

                {metricCol !== "__count__" && (
                  <div className="flex rounded-xl bg-slate-200 dark:bg-slate-800 p-1 text-[11px] font-semibold">
                    {(["sum", "avg", "max", "min"] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => setAggregation(mode)}
                        className={`flex-1 py-1 rounded-lg uppercase tracking-wider transition-all ${
                          aggregation === mode 
                            ? "bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm" 
                            : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
                        }`}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Color Palette */}
            <div>
              <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Palette className="w-3.5 h-3.5" />
                4. Theme & Color Palette
              </label>
              <div className="grid grid-cols-5 gap-1.5">
                {(["indigo", "emerald", "rose", "ocean", "midnight"] as PaletteType[]).map((p) => {
                  const pal = COLOR_PALETTES[p];
                  const active = palette === p;
                  return (
                    <button
                      key={p}
                      onClick={() => setPalette(p)}
                      style={{ backgroundColor: pal.primary }}
                      className={`h-7 rounded-xl flex items-center justify-center transition-all ${
                        active ? "ring-2 ring-offset-2 ring-indigo-600 scale-105" : "opacity-80 hover:opacity-100"
                      }`}
                      title={p.toUpperCase()}
                    >
                      {active && <Check className="w-3.5 h-3.5 text-white" />}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Filters & Limits */}
            <div className="space-y-3 pt-2 border-t border-slate-200 dark:border-slate-800">
              <div className="flex justify-between items-center text-xs font-bold text-slate-600 dark:text-slate-400">
                <span>Top N Categories: {topN}</span>
                <input 
                  type="range" 
                  min="5" 
                  max="50" 
                  step="5"
                  value={topN}
                  onChange={(e) => setTopN(parseInt(e.target.value))}
                  className="w-24 accent-indigo-600 cursor-pointer"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-500 mb-1">Sorting Order</label>
                <div className="flex rounded-xl bg-slate-200 dark:bg-slate-800 p-1 text-[10px] font-semibold">
                  {[
                    { id: "desc", label: "High → Low" },
                    { id: "asc", label: "Low → High" },
                    { id: "natural", label: "Natural / Order" },
                  ].map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setSortOrder(s.id as any)}
                      className={`flex-1 py-1 rounded-lg transition-all ${
                        sortOrder === s.id 
                          ? "bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm" 
                          : "text-slate-500 hover:text-slate-900"
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

          </div>

          {/* Visualization Stage & Main Display */}
          <div className="lg:col-span-3 p-6 flex flex-col bg-white dark:bg-slate-950 overflow-hidden">
            
            {/* View Mode Tabs & Quick Stats */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-900 p-1 rounded-2xl">
                <button
                  onClick={() => setActiveTab("chart")}
                  className={`px-4 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all ${
                    activeTab === "chart"
                      ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-white"
                  }`}
                >
                  <BarChart3 className="w-3.5 h-3.5" />
                  Interactive Chart
                </button>
                <button
                  onClick={() => setActiveTab("table")}
                  className={`px-4 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all ${
                    activeTab === "table"
                      ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-white"
                  }`}
                >
                  <Table className="w-3.5 h-3.5" />
                  Data Table ({chartData.length} items)
                </button>
              </div>

              {/* Stat Summary Pills & Original PDF Link */}
              <div className="flex items-center gap-3 text-xs font-semibold">
                <a
                  href={`${apiBase}/api/file/${selectedFolder}/${selectedFile.replace('.csv', '.pdf')}`}
                  target="_blank"
                  className="px-3 py-1 rounded-full bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300 hover:bg-purple-100 flex items-center gap-1 border border-purple-200 dark:border-purple-800 transition-all"
                  title="View original generated PDF figure"
                >
                  <Download className="w-3 h-3" />
                  Original PDF
                </a>
                <span className="px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-300">
                  Rows: <strong className="text-slate-900 dark:text-white">{rows.length}</strong>
                </span>
                <span className="px-3 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                  Max: <strong>{maxValue.toLocaleString()}</strong>
                </span>
              </div>
            </div>

            {/* Display Area */}
            <div className="flex-1 flex flex-col justify-center items-center overflow-auto relative min-h-[380px]">
              
              {loading ? (
                <div className="flex flex-col items-center justify-center space-y-3">
                  <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
                  <p className="text-sm font-medium text-slate-500">Loading dataset from {selectedFolder}/{selectedFile}...</p>
                </div>
              ) : error ? (
                <div className="p-6 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-2xl text-center text-red-600 dark:text-red-400 max-w-md">
                  <p className="text-sm font-bold">{error}</p>
                </div>
              ) : chartData.length === 0 ? (
                <div className="text-center p-8 border-2 border-dashed rounded-3xl border-slate-200 dark:border-slate-800 text-slate-400">
                  No data points found for selected configuration.
                </div>
              ) : activeTab === "chart" ? (
                
                /* --- DYNAMIC CUSTOM SVG / HTML CHART CANVAS --- */
                <div className="w-full h-full flex flex-col justify-between p-4">
                  
                  {/* Vertical Bar / Area / Line Chart */}
                  {(chartType === "bar" || chartType === "line" || chartType === "area") && (
                    <div className="w-full flex-1 flex items-end gap-3 pt-8 pb-12 px-4 relative border-b border-l border-slate-200 dark:border-slate-800 min-h-[300px]">
                      
                      {/* Background Gridlines */}
                      <div className="absolute inset-0 flex flex-col justify-between pointer-events-none opacity-20">
                        {[1, 0.75, 0.5, 0.25, 0].map((step, idx) => (
                          <div key={idx} className="border-b border-dashed border-slate-400 w-full flex justify-between text-[10px] text-slate-400">
                            <span>{Math.round(maxValue * step)}</span>
                          </div>
                        ))}
                      </div>

                      {chartData.map((item, idx) => {
                        const heightPct = Math.max((item.value / maxValue) * 100, 3);
                        const color = activePalette.gradient[idx % activePalette.gradient.length];

                        return (
                          <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end group relative z-10">
                            
                            {/* Hover Value Tooltip */}
                            <div className="opacity-0 group-hover:opacity-100 transition-all duration-200 absolute -top-9 bg-slate-900 text-white text-[11px] font-bold px-2.5 py-1 rounded-lg shadow-lg pointer-events-none whitespace-nowrap">
                              {item.label}: {item.value.toLocaleString()}
                            </div>

                            {/* Bar Graphic */}
                            <div
                              style={{ 
                                height: `${heightPct}%`,
                                backgroundColor: color
                              }}
                              className="w-full max-w-[54px] rounded-t-xl transition-all duration-500 hover:brightness-110 shadow-md group-hover:scale-105 origin-bottom"
                            />

                            {/* X Label */}
                            <span className="mt-3 text-[11px] font-semibold text-slate-600 dark:text-slate-400 truncate max-w-[70px] text-center capitalize">
                              {item.label}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Horizontal Bar Chart */}
                  {chartType === "hbar" && (
                    <div className="w-full flex-1 space-y-3 py-4 overflow-y-auto max-h-[340px] pr-3">
                      {chartData.map((item, idx) => {
                        const widthPct = Math.max((item.value / maxValue) * 100, 4);
                        const color = activePalette.gradient[idx % activePalette.gradient.length];

                        return (
                          <div key={idx} className="space-y-1 group">
                            <div className="flex justify-between text-xs font-semibold text-slate-700 dark:text-slate-300">
                              <span className="truncate max-w-[340px] capitalize">{item.label}</span>
                              <span className="text-slate-900 dark:text-white font-bold">{item.value.toLocaleString()}</span>
                            </div>
                            <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-3.5 overflow-hidden p-0.5">
                              <div
                                style={{
                                  width: `${widthPct}%`,
                                  backgroundColor: color
                                }}
                                className="h-full rounded-full transition-all duration-700 group-hover:brightness-110"
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Donut / Pie Chart */}
                  {chartType === "pie" && (
                    <div className="w-full flex-1 flex flex-col md:flex-row items-center justify-center gap-8 py-4">
                      {/* CSS Conical Gradient Donut Representation */}
                      <div className="relative w-56 h-56 rounded-full shadow-inner flex items-center justify-center p-4 bg-slate-100 dark:bg-slate-800">
                        <div 
                          className="w-full h-full rounded-full shadow-lg"
                          style={{
                            background: `conic-gradient(${chartData.map((item, idx) => {
                              const sum = chartData.reduce((a, b) => a + b.value, 0);
                              const prev = chartData.slice(0, idx).reduce((a, b) => a + b.value, 0);
                              const startPct = (prev / sum) * 100;
                              const endPct = ((prev + item.value) / sum) * 100;
                              const color = activePalette.gradient[idx % activePalette.gradient.length];
                              return `${color} ${startPct}% ${endPct}%`;
                            }).join(", ")})`
                          }}
                        />
                        {/* Donut Center */}
                        <div className="absolute w-28 h-28 bg-white dark:bg-slate-950 rounded-full flex flex-col items-center justify-center text-center shadow-md">
                          <span className="text-[10px] font-bold text-slate-400 uppercase">Total</span>
                          <span className="text-sm font-bold text-slate-900 dark:text-white">
                            {chartData.reduce((a, b) => a + b.value, 0).toLocaleString()}
                          </span>
                        </div>
                      </div>

                      {/* Legend */}
                      <div className="grid grid-cols-2 gap-2 max-h-[220px] overflow-y-auto">
                        {chartData.map((item, idx) => {
                          const color = activePalette.gradient[idx % activePalette.gradient.length];
                          return (
                            <div key={idx} className="flex items-center gap-2 text-xs">
                              <span style={{ backgroundColor: color }} className="w-3 h-3 rounded-full flex-shrink-0" />
                              <span className="text-slate-600 dark:text-slate-400 truncate max-w-[130px] capitalize">{item.label}:</span>
                              <strong className="text-slate-900 dark:text-white">{item.value.toLocaleString()}</strong>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Scatter Plot */}
                  {chartType === "scatter" && (
                    <div className="w-full flex-1 relative border-b border-l border-slate-200 dark:border-slate-800 min-h-[300px] p-6 flex items-end">
                      {chartData.map((item, idx) => {
                        const leftPct = (idx / Math.max(chartData.length - 1, 1)) * 90 + 5;
                        const bottomPct = Math.max((item.value / maxValue) * 85 + 5, 5);
                        const color = activePalette.gradient[idx % activePalette.gradient.length];

                        return (
                          <div
                            key={idx}
                            style={{
                              left: `${leftPct}%`,
                              bottom: `${bottomPct}%`,
                              backgroundColor: color
                            }}
                            className="absolute w-5 h-5 rounded-full shadow-lg border-2 border-white dark:border-slate-900 transform -translate-x-1/2 translate-y-1/2 hover:scale-150 transition-all cursor-pointer group"
                          >
                            <div className="opacity-0 group-hover:opacity-100 transition-all absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-900 text-white text-[10px] font-bold px-2 py-0.5 rounded shadow pointer-events-none whitespace-nowrap">
                              {item.label}: {item.value}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                </div>
              ) : (
                
                /* Data Summary Table Tab */
                <div className="w-full h-full overflow-auto max-h-[360px]">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-bold uppercase text-[10px]">
                        <th className="py-2.5 px-4">#</th>
                        <th className="py-2.5 px-4">{xAxisCol || "Category"}</th>
                        <th className="py-2.5 px-4 text-right">Computed Value ({metricCol})</th>
                        <th className="py-2.5 px-4 text-right">Record Count</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/50">
                      {chartData.map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors">
                          <td className="py-2 px-4 text-slate-400 font-mono">{idx + 1}</td>
                          <td className="py-2 px-4 font-semibold text-slate-800 dark:text-slate-200 capitalize">{row.label}</td>
                          <td className="py-2 px-4 text-right font-bold text-indigo-600 dark:text-indigo-400">{row.value.toLocaleString()}</td>
                          <td className="py-2 px-4 text-right text-slate-500">{row.count.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

            </div>

          </div>

        </div>

      </div>
    </div>
  );
}

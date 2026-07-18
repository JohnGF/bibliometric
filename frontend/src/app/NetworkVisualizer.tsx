"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { X, Sliders, Search, RefreshCw, ZoomIn, ZoomOut, Info, Network, Award, BookOpen } from "lucide-react";

interface NetworkVisualizerProps {
  apiBase: string;
  onClose: () => void;
}

interface Node {
  id: number;
  name: string;
  citations: number;
  publications: number;
  pagerank: number;
  community: number;
  affiliations: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  isDragging?: boolean;
}

interface Edge {
  sourceId: number;
  destId: number;
  sourceName: string;
  destName: string;
  weight: number;
}

// Modern harmonious HSL colors for up to 10 communities
const COMMUNITY_COLORS = [
  "hsl(217, 91%, 60%)", // Blue
  "hsl(142, 71%, 45%)", // Green
  "hsl(280, 87%, 65%)", // Purple
  "hsl(32, 98%, 56%)",  // Orange
  "hsl(350, 89%, 60%)", // Pink
  "hsl(190, 90%, 50%)", // Cyan
  "hsl(48, 96%, 53%)",  // Yellow
  "hsl(160, 84%, 39%)", // Teal
  "hsl(262, 83%, 58%)", // Indigo
  "hsl(0, 0%, 60%)"      // Grey fallback
];

export default function NetworkVisualizer({ apiBase, onClose }: NetworkVisualizerProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter States
  const [minCitations, setMinCitations] = useState(0);
  const [minPublications, setMinPublications] = useState(1);
  const [nodeSizing, setNodeSizing] = useState<"citations" | "publications" | "pagerank">("publications");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCommunity, setSelectedCommunity] = useState<number | null>(null);

  // Physics parameter states
  const [repulsion, setRepulsion] = useState(400);
  const [springStrength, setSpringStrength] = useState(0.04);
  const [gravity, setGravity] = useState(0.02);
  const [damping, setDamping] = useState(0.85);

  // Interactive UI states
  const [hoveredNode, setHoveredNode] = useState<Node | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  // Ticks state to trigger React re-renders for the simulation
  const [tick, setTick] = useState(0);

  const containerRef = useRef<SVGSVGElement>(null);
  const dragNodeRef = useRef<Node | null>(null);
  const requestRef = useRef<number | null>(null);

  // Dimensions of SVG canvas
  const width = 800;
  const height = 600;

  // 1. Fetch and Parse Datasets on Mount
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch nodes & edges in parallel
        const [nodesRes, edgesRes] = await Promise.all([
          fetch(`${apiBase}/results/network_nodes.csv`),
          fetch(`${apiBase}/results/network_edges.csv`)
        ]);

        if (!nodesRes.ok || !edgesRes.ok) {
          throw new Error("Failed to load network results from FastAPI. Run analysis first.");
        }

        const nodesText = await nodesRes.text();
        const edgesText = await edgesRes.text();

        // Robust CSV Parser
        const parsedNodes = parseCSVNodes(nodesText);
        const parsedEdges = parseCSVEdges(edgesText);

        if (parsedNodes.length === 0) {
          throw new Error("Nodes dataset is empty.");
        }

        // Initialize positions in a circle layout
        const initializedNodes = parsedNodes.map((n, i) => {
          const angle = (i / parsedNodes.length) * 2 * Math.PI;
          const radius = 100 + Math.random() * 100;
          return {
            ...n,
            x: width / 2 + Math.cos(angle) * radius,
            y: height / 2 + Math.sin(angle) * radius,
            vx: 0,
            vy: 0
          };
        });

        setNodes(initializedNodes);
        setEdges(parsedEdges);
      } catch (err: any) {
        console.error("Data loading error:", err);
        setError(err.message || "Failed to load visualization data");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [apiBase]);

  // CSV Parsing Utils
  const parseCSVNodes = (text: string): Omit<Node, "x" | "y" | "vx" | "vy">[] => {
    const lines = text.split("\n").filter(l => l.trim() !== "");
    if (lines.length <= 1) return [];
    
    return lines.slice(1).map(line => {
      const columns = [];
      let current = "";
      let inQuotes = false;
      
      for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
          if (inQuotes && line[i + 1] === '"') {
            current += '"';
            i++; // skip next quote
          } else {
            inQuotes = !inQuotes;
          }
        } else if (char === ',' && !inQuotes) {
          columns.push(current.trim());
          current = "";
        } else {
          current += char;
        }
      }
      columns.push(current.trim());

      // Validate columns count (vertex, partition, pagerank, author_name, ...)
      if (columns.length < 4) return null;

      const vertex = parseInt(columns[0]);
      if (isNaN(vertex)) return null;

      const partition = parseInt(columns[1]) || 0;
      const pagerank = parseFloat(columns[2]) || 0;
      
      const author_name = columns[3] ? columns[3].replace(/^["']|["']$/g, "").trim() : "";
      if (!author_name || author_name.toLowerCase() === "unknown" || author_name.toLowerCase() === "nan" || author_name.toLowerCase() === "none") {
        return null;
      }

      const total_citations = parseInt(columns[4]) || 0;
      const num_publications = parseInt(columns[5]) || 1;
      const affiliations_str = columns[6] ? columns[6].replace(/^["']|["']$/g, "").trim() : "";

      return {
        id: vertex,
        name: author_name,
        citations: total_citations,
        publications: num_publications,
        pagerank: pagerank,
        community: partition,
        affiliations: affiliations_str
      };
    }).filter((n): n is Omit<Node, "x" | "y" | "vx" | "vy"> => n !== null);
  };

  const parseCSVEdges = (text: string): Edge[] => {
    const lines = text.split("\n").filter(l => l.trim() !== "");
    if (lines.length <= 1) return [];

    return lines.slice(1).map(line => {
      const parts = line.split(",");
      if (parts.length < 5) return null;

      const sourceName = parts[0] ? parts[0].replace(/^["']|["']$/g, "").trim() : "";
      const destName = parts[1] ? parts[1].replace(/^["']|["']$/g, "").trim() : "";
      const weight = parseFloat(parts[2]);
      const sourceId = parseInt(parts[3]);
      const destId = parseInt(parts[4]);

      if (!sourceName || !destName || isNaN(weight) || isNaN(sourceId) || isNaN(destId)) {
        return null;
      }

      return {
        sourceName,
        destName,
        weight,
        sourceId,
        destId
      };
    }).filter((e): e is Edge => e !== null);
  };

  // 2. Physics Simulation Loop
  useEffect(() => {
    if (loading || error || nodes.length === 0) return;

    const runSimulation = () => {
      setNodes(prevNodes => {
        // Create lookup dictionary for speedy node reference
        const nodeMap = new Map(prevNodes.map(n => [n.id, n]));

        // Calculate forces
        const nLen = prevNodes.length;

        // 1. Repulsion (Coulomb-like force)
        for (let i = 0; i < nLen; i++) {
          const u = prevNodes[i];
          for (let j = i + 1; j < nLen; j++) {
            const v = prevNodes[j];
            const dx = v.x - u.x;
            const dy = v.y - u.y;
            const distSq = dx * dx + dy * dy + 1;
            const dist = Math.sqrt(distSq);

            if (dist < 400) {
              const force = repulsion / distSq;
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;

              if (!u.isDragging) {
                u.vx -= fx;
                u.vy -= fy;
              }
              if (!v.isDragging) {
                v.vx += fx;
                v.vy += fy;
              }
            }
          }
        }

        // 2. Spring Attraction (Hooke's Law for edges)
        edges.forEach(edge => {
          const u = nodeMap.get(edge.sourceId);
          const v = nodeMap.get(edge.destId);

          if (u && v) {
            const dx = v.x - u.x;
            const dy = v.y - u.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1.0;
            const restLength = 120;
            const force = (dist - restLength) * springStrength * edge.weight;

            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (!u.isDragging) {
              u.vx += fx;
              u.vy += fy;
            }
            if (!v.isDragging) {
              v.vx -= fx;
              v.vy -= fy;
            }
          }
        });

        // 3. Central Gravity & Update Positions
        const updated = prevNodes.map(node => {
          if (node.isDragging) return node;

          // Pull to center
          const dx = width / 2 - node.x;
          const dy = height / 2 - node.y;
          node.vx += dx * gravity;
          node.vy += dy * gravity;

          // Apply velocity and damping
          node.vx *= damping;
          node.vy *= damping;
          
          // Clamp velocity to avoid explosion
          const speed = Math.sqrt(node.vx * node.vx + node.vy * node.vy);
          if (speed > 15) {
            node.vx = (node.vx / speed) * 15;
            node.vy = (node.vy / speed) * 15;
          }

          node.x += node.vx;
          node.y += node.vy;

          // Bounding box clamping
          node.x = Math.max(40, Math.min(width - 40, node.x));
          node.y = Math.max(40, Math.min(height - 40, node.y));

          return node;
        });

        return updated;
      });

      setTick(t => t + 1);
      requestRef.current = requestAnimationFrame(runSimulation);
    };

    requestRef.current = requestAnimationFrame(runSimulation);

    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, [loading, error, repulsion, springStrength, gravity, damping, edges]);

  // 3. Dynamic Filter Calculations
  const filteredNodes = useMemo(() => {
    return nodes.filter(node => {
      if (node.citations < minCitations) return false;
      if (node.publications < minPublications) return false;
      if (selectedCommunity !== null && node.community !== selectedCommunity) return false;
      return true;
    });
  }, [nodes, minCitations, minPublications, selectedCommunity]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map(n => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    return edges.filter(edge => {
      return filteredNodeIds.has(edge.sourceId) && filteredNodeIds.has(edge.destId);
    });
  }, [edges, filteredNodeIds]);

  // Max stats for relative sizing calculations
  const maxStats = useMemo(() => {
    let maxCitations = 1;
    let maxPublications = 1;
    let maxPagerank = 0.0001;
    nodes.forEach(n => {
      if (n.citations > maxCitations) maxCitations = n.citations;
      if (n.publications > maxPublications) maxPublications = n.publications;
      if (n.pagerank > maxPagerank) maxPagerank = n.pagerank;
    });
    return { maxCitations, maxPublications, maxPagerank };
  }, [nodes]);

  // Community Statistics & Count
  const communities = useMemo(() => {
    const counts: Record<number, number> = {};
    nodes.forEach(n => {
      counts[n.community] = (counts[n.community] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([id, count]) => ({ id: parseInt(id), count }))
      .sort((a, b) => b.count - a.count);
  }, [nodes]);

  // Highlight connections for searched nodes or selected node
  const activeSearchLower = searchQuery.toLowerCase();
  const highlightedIds = useMemo(() => {
    const ids = new Set<number>();
    if (activeSearchLower) {
      nodes.forEach(n => {
        if (n.name.toLowerCase().includes(activeSearchLower)) {
          ids.add(n.id);
          // Highlight direct neighbors
          edges.forEach(e => {
            if (e.sourceId === n.id) ids.add(e.destId);
            if (e.destId === n.id) ids.add(e.sourceId);
          });
        }
      });
    } else if (selectedNode) {
      ids.add(selectedNode.id);
      edges.forEach(e => {
        if (e.sourceId === selectedNode.id) ids.add(e.destId);
        if (e.destId === selectedNode.id) ids.add(e.sourceId);
      });
    }
    return ids;
  }, [nodes, edges, activeSearchLower, selectedNode]);

  // Check if we are in highlight mode
  const isHighlightMode = activeSearchLower.length > 0 || selectedNode !== null;

  // 4. Mouse Drag Handlers
  const handleMouseDown = (node: Node, e: React.MouseEvent) => {
    e.preventDefault();
    node.isDragging = true;
    dragNodeRef.current = node;
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!dragNodeRef.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    
    // Convert client coordinates based on zoom and pan
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    // Scale back pan & zoom
    const svgX = (clientX - pan.x) / zoom;
    const svgY = (clientY - pan.y) / zoom;

    dragNodeRef.current.x = Math.max(20, Math.min(width - 20, svgX));
    dragNodeRef.current.y = Math.max(20, Math.min(height - 20, svgY));
    dragNodeRef.current.vx = 0;
    dragNodeRef.current.vy = 0;
  };

  const handleMouseUp = () => {
    if (dragNodeRef.current) {
      dragNodeRef.current.isDragging = false;
      dragNodeRef.current = null;
    }
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
  };

  // Node Size Calculator
  const getNodeRadius = (node: Node) => {
    const baseSize = 8;
    if (nodeSizing === "citations") {
      const ratio = Math.log(node.citations + 1) / Math.log(maxStats.maxCitations + 1);
      return baseSize + ratio * 20;
    } else if (nodeSizing === "pagerank") {
      const ratio = node.pagerank / maxStats.maxPagerank;
      return baseSize + ratio * 25;
    } else {
      const ratio = node.publications / maxStats.maxPublications;
      return baseSize + ratio * 15;
    }
  };

  const handleResetLayout = () => {
    setNodes(prev => {
      return prev.map((n, i) => {
        const angle = (i / prev.length) * 2 * Math.PI;
        const radius = 100 + Math.random() * 100;
        return {
          ...n,
          x: width / 2 + Math.cos(angle) * radius,
          y: height / 2 + Math.sin(angle) * radius,
          vx: 0,
          vy: 0
        };
      });
    });
  };

  return (
    <div className="fixed inset-0 bg-slate-950/98 backdrop-blur-md z-50 flex flex-col text-slate-100 animate-in fade-in duration-200">
      {/* Header bar */}
      <header className="px-6 py-4 bg-slate-900/50 border-b border-slate-800 flex justify-between items-center shadow-lg">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 rounded-xl border border-blue-500/20 text-blue-400">
            <Network className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Co-authorship Network Sandbox</h1>
            <p className="text-xs text-slate-400">Interactive RAPIDS cuGraph Partitioning & Layout Tuner</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={handleResetLayout} 
            className="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition-all border border-slate-700/50 flex items-center gap-2 text-xs font-semibold"
            title="Reset node physics arrangement"
          >
            <RefreshCw className="w-4 h-4" /> Reset Layout
          </button>
          <button 
            onClick={onClose} 
            className="p-2.5 bg-red-950/20 hover:bg-red-900/40 text-red-400 border border-red-900/30 rounded-xl transition-all shadow-sm"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Content Layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 overflow-hidden">
        {/* Left Side: Parameters tuning drawer */}
        <aside className="bg-slate-900/40 border-r border-slate-900 p-6 overflow-y-auto space-y-6 select-none custom-scrollbar">
          <div className="flex items-center gap-2 text-slate-400 uppercase tracking-wider text-xs font-bold mb-2">
            <Sliders className="w-4 h-4 text-blue-500" /> Control Knobs
          </div>

          {/* Sizing & Filtering */}
          <div className="space-y-4 bg-slate-900/50 p-4 rounded-xl border border-slate-800/80">
            <div>
              <label className="block text-xs text-slate-400 font-semibold mb-2">Node Diameter Scales By</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => setNodeSizing("publications")}
                  className={`py-1.5 px-2 rounded-lg text-[10px] font-medium border transition-all ${nodeSizing === "publications" ? "bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-900/20" : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"}`}
                >
                  Pubs
                </button>
                <button
                  onClick={() => setNodeSizing("citations")}
                  className={`py-1.5 px-2 rounded-lg text-[10px] font-medium border transition-all ${nodeSizing === "citations" ? "bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-900/20" : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"}`}
                >
                  Cites
                </button>
                <button
                  onClick={() => setNodeSizing("pagerank")}
                  className={`py-1.5 px-2 rounded-lg text-[10px] font-medium border transition-all ${nodeSizing === "pagerank" ? "bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-900/20" : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"}`}
                >
                  Influence
                </button>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-slate-400">Min Citations</span>
                <span className="text-blue-400">{minCitations}</span>
              </div>
              <input
                type="range"
                min="0"
                max="200"
                value={minCitations}
                onChange={(e) => setMinCitations(parseInt(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-slate-400">Min Papers Published</span>
                <span className="text-blue-400">{minPublications}</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={minPublications}
                onChange={(e) => setMinPublications(parseInt(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
          </div>

          {/* Physics parameters */}
          <div className="space-y-4 bg-slate-900/50 p-4 rounded-xl border border-slate-800/80">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Physics Forces</h3>
            
            <div>
              <div className="flex justify-between text-xs mb-1 font-semibold">
                <span className="text-slate-400">Node Repulsion (Spacing)</span>
                <span className="text-blue-400">{repulsion}</span>
              </div>
              <input
                type="range"
                min="100"
                max="1000"
                step="50"
                value={repulsion}
                onChange={(e) => setRepulsion(parseInt(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1 font-semibold">
                <span className="text-slate-400">Spring Force (Attraction)</span>
                <span className="text-blue-400">{springStrength.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.01"
                max="0.15"
                step="0.01"
                value={springStrength}
                onChange={(e) => setSpringStrength(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1 font-semibold">
                <span className="text-slate-400">Central Gravity</span>
                <span className="text-blue-400">{gravity.toFixed(3)}</span>
              </div>
              <input
                type="range"
                min="0.005"
                max="0.08"
                step="0.005"
                value={gravity}
                onChange={(e) => setGravity(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
          </div>

          {/* Communities & Legend */}
          <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/80 space-y-3">
            <div className="flex justify-between items-center mb-1">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Louvain Groups</h3>
              {selectedCommunity !== null && (
                <button
                  onClick={() => setSelectedCommunity(null)}
                  className="text-[10px] text-red-400 font-bold hover:underline"
                >
                  Clear Filter
                </button>
              )}
            </div>
            <div className="space-y-1.5 max-h-[160px] overflow-y-auto pr-1 custom-scrollbar">
              {communities.slice(0, 10).map((comm, idx) => {
                const color = COMMUNITY_COLORS[comm.id % COMMUNITY_COLORS.length];
                const isSelected = selectedCommunity === comm.id;
                return (
                  <div
                    key={comm.id}
                    onClick={() => setSelectedCommunity(isSelected ? null : comm.id)}
                    className={`flex items-center justify-between px-2.5 py-1 rounded-lg text-xs cursor-pointer border transition-all ${isSelected ? "bg-slate-800 border-slate-700 text-white font-bold" : "hover:bg-slate-850 border-transparent text-slate-400"}`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                      <span>Group {comm.id}</span>
                    </div>
                    <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded-md font-mono">{comm.count} authors</span>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>

        {/* Center: Graph Viewer */}
        <main className="lg:col-span-2 relative border-r border-slate-900 flex flex-col bg-slate-950/60">
          {/* Zoom controls, Search input overlay */}
          <div className="absolute top-4 left-4 right-4 z-10 flex gap-2 justify-between items-center select-none pointer-events-none">
            <div className="flex gap-1.5 bg-slate-900/90 border border-slate-800 rounded-xl p-1.5 pointer-events-auto backdrop-blur shadow-xl">
              <button 
                onClick={() => setZoom(z => Math.min(3.0, z + 0.1))} 
                className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button 
                onClick={() => setZoom(z => Math.max(0.4, z - 0.1))} 
                className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <button 
                onClick={() => { setZoom(1.0); setPan({ x: 0, y: 0 }); }} 
                className="px-2 text-[10px] hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors font-bold uppercase"
              >
                Recenter
              </button>
            </div>

            <div className="relative w-64 pointer-events-auto">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Find author..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-8 py-2 bg-slate-900/90 border border-slate-800 focus:border-blue-500/80 rounded-xl text-xs placeholder-slate-500 outline-none transition-all shadow-xl font-medium"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs font-bold font-sans"
                >
                  ×
                </button>
              )}
            </div>
          </div>

          {/* SVG Graphic viewport */}
          <div className="flex-1 overflow-hidden relative cursor-grab active:cursor-grabbing">
            {loading ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
                <p className="text-sm text-slate-400 font-semibold animate-pulse">Running Physics Layout Engine...</p>
              </div>
            ) : error ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center gap-4">
                <div className="p-4 bg-red-950/20 text-red-500 border border-red-900/30 rounded-2xl">
                  <Info className="w-8 h-8 mx-auto mb-2" />
                  <p className="font-bold text-sm">{error}</p>
                </div>
              </div>
            ) : (
              <svg
                ref={containerRef}
                viewBox={`0 0 ${width} ${height}`}
                className="w-full h-full select-none"
                style={{ background: "radial-gradient(circle at center, #0b1329 0%, #030712 100%)" }}
                onMouseMove={(e) => {
                  if (e.buttons === 4 || (e.buttons === 1 && e.shiftKey)) { // Middle mouse or Shift + Left click to pan
                    setPan(p => ({ x: p.x + e.movementX, y: p.y + e.movementY }));
                  }
                }}
              >
                {/* SVG Render Tree */}
                <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                  
                  {/* Springs / Links */}
                  <g className="links">
                    {filteredEdges.map((edge, idx) => {
                      const u = nodes.find(n => n.id === edge.sourceId);
                      const v = nodes.find(n => n.id === edge.destId);
                      if (!u || !v) return null;

                      // Highlight status
                      const isHighlighted = isHighlightMode && highlightedIds.has(u.id) && highlightedIds.has(v.id);
                      const isDimmed = isHighlightMode && (!highlightedIds.has(u.id) || !highlightedIds.has(v.id));

                      return (
                        <line
                          key={idx}
                          x1={u.x}
                          y1={u.y}
                          x2={v.x}
                          y2={v.y}
                          stroke={isHighlighted ? "hsl(217, 91%, 60%)" : "rgba(148, 163, 184, 0.15)"}
                          strokeWidth={isHighlighted ? 2.5 : Math.min(6, 1 + edge.weight * 1.5)}
                          strokeOpacity={isDimmed ? 0.04 : 0.6}
                          className="transition-all duration-150"
                        />
                      );
                    })}
                  </g>

                  {/* Authors / Nodes */}
                  <g className="nodes">
                    {filteredNodes.map((node) => {
                      const radius = getNodeRadius(node);
                      const color = COMMUNITY_COLORS[node.community % COMMUNITY_COLORS.length];
                      
                      // Highlight logic
                      const isSearched = searchQuery && node.name.toLowerCase().includes(activeSearchLower);
                      const isHighlighted = isHighlightMode && highlightedIds.has(node.id);
                      const isDimmed = isHighlightMode && !highlightedIds.has(node.id);

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${node.x}, ${node.y})`}
                          className="cursor-pointer group"
                          onMouseDown={(e) => handleMouseDown(node, e)}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedNode(selectedNode?.id === node.id ? null : node);
                          }}
                          onMouseEnter={() => setHoveredNode(node)}
                          onMouseLeave={() => setHoveredNode(null)}
                        >
                          {/* Outer glow ring */}
                          <circle
                            r={radius + 4}
                            fill="none"
                            stroke={isSearched ? "#ffffff" : color}
                            strokeWidth={isSearched ? 2.5 : 1.5}
                            strokeOpacity={isHighlighted || isSearched ? 1.0 : (isDimmed ? 0.05 : 0.4)}
                            className="group-hover:scale-125 transition-transform duration-200 ease-out"
                          />
                          
                          {/* Solid colored core */}
                          <circle
                            r={radius}
                            fill={color}
                            fillOpacity={isDimmed ? 0.15 : 0.9}
                            className="transition-opacity duration-200"
                          />

                          {/* Highly readable text labels */}
                          {(radius > 11 || isHighlighted || isSearched) && (
                            <text
                              y={radius + 14}
                              textAnchor="middle"
                              fill={isSearched ? "#ffffff" : (isDimmed ? "rgba(148, 163, 184, 0.15)" : "#e2e8f0")}
                              className={`text-[9px] select-none font-bold pointer-events-none transition-all duration-200 ${isHighlighted || isSearched ? "text-[11px] fill-white" : ""}`}
                              style={{ textShadow: "0 2px 4px rgba(0,0,0,0.9)" }}
                            >
                              {node.name}
                            </text>
                          )}
                        </g>
                      );
                    })}
                  </g>
                </g>
              </svg>
            )}
          </div>
        </main>

        {/* Right Side: Selected node metadata / full information */}
        <aside className="bg-slate-900/40 border-l border-slate-900 p-6 flex flex-col justify-between overflow-y-auto custom-scrollbar select-none">
          {/* Main inspector block */}
          <div className="space-y-6">
            <div className="flex items-center gap-2 text-slate-400 uppercase tracking-wider text-xs font-bold mb-2">
              <Info className="w-4 h-4 text-blue-500" /> Node Inspector
            </div>

            {/* Display hovered or selected node */}
            {(hoveredNode || selectedNode) ? (
              (() => {
                const node = hoveredNode || selectedNode!;
                const color = COMMUNITY_COLORS[node.community % COMMUNITY_COLORS.length];
                return (
                  <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-200">
                    <div className="p-4 bg-slate-900/80 rounded-2xl border border-slate-800 shadow-xl space-y-4">
                      {/* Avatar header */}
                      <div className="flex items-start gap-3">
                        <div 
                          className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg flex-shrink-0 shadow-lg"
                          style={{ backgroundColor: color }}
                        >
                          {node.name.charAt(0)}
                        </div>
                        <div>
                          <h4 className="font-bold text-slate-100 text-sm leading-tight">{node.name}</h4>
                          <span className="inline-block mt-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700/50">
                            Community Group {node.community}
                          </span>
                        </div>
                      </div>

                      {/* Stat grid */}
                      <div className="grid grid-cols-2 gap-3.5 pt-2">
                        <div className="bg-slate-950/40 p-3 rounded-xl border border-slate-800/80 flex flex-col gap-0.5">
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider flex items-center gap-1">
                            <BookOpen className="w-3 h-3 text-emerald-400" /> Papers
                          </span>
                          <span className="text-base font-extrabold text-slate-100">{node.publications}</span>
                        </div>
                        <div className="bg-slate-950/40 p-3 rounded-xl border border-slate-800/80 flex flex-col gap-0.5">
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider flex items-center gap-1">
                            <Award className="w-3 h-3 text-amber-400" /> Citations
                          </span>
                          <span className="text-base font-extrabold text-slate-100">{node.citations}</span>
                        </div>
                      </div>

                      {/* Affiliations list */}
                      {node.affiliations && (
                        <div className="pt-2 space-y-1">
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Primary Affiliations</span>
                          <p className="text-xs text-slate-300 font-medium leading-relaxed bg-slate-950/20 p-2.5 rounded-lg border border-slate-800/30">
                            {node.affiliations}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Edge connections list */}
                    <div className="space-y-2.5">
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Top Co-authors</span>
                      <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1 custom-scrollbar">
                        {edges
                          .filter(e => e.sourceId === node.id || e.destId === node.id)
                          .sort((a, b) => b.weight - a.weight)
                          .map((edge, idx) => {
                            const isSource = edge.sourceId === node.id;
                            const coAuthorName = isSource ? edge.destName : edge.sourceName;
                            const coAuthorId = isSource ? edge.destId : edge.sourceId;
                            const coAuthorNode = nodes.find(n => n.id === coAuthorId);
                            const coAuthorComm = coAuthorNode?.community ?? 0;
                            const coAuthorColor = COMMUNITY_COLORS[coAuthorComm % COMMUNITY_COLORS.length];
                            
                            return (
                              <div
                                key={idx}
                                onClick={() => {
                                  if (coAuthorNode) {
                                    setSelectedNode(coAuthorNode);
                                  }
                                }}
                                className="flex items-center justify-between p-2.5 bg-slate-900/30 hover:bg-slate-800/50 rounded-xl border border-slate-800/20 transition-all cursor-pointer group"
                              >
                                <div className="flex items-center gap-2 truncate">
                                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: coAuthorColor }} />
                                  <span className="text-xs text-slate-300 truncate font-semibold group-hover:text-blue-400">{coAuthorName}</span>
                                </div>
                                <span className="text-[9px] bg-slate-800 px-2 py-0.5 rounded-md font-bold text-slate-400 group-hover:bg-blue-950 group-hover:text-blue-300">
                                  Weight: {edge.weight}
                                </span>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  </div>
                );
              })()
            ) : (
              <div className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-slate-800 rounded-2xl text-center gap-2">
                <Network className="w-8 h-8 text-slate-700" />
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">No Node Selected</p>
                <p className="text-[11px] text-slate-500">Hover or click a node in the network to inspect detailed co-authorship credentials.</p>
              </div>
            )}
          </div>

          {/* Quick tips footer */}
          <div className="p-4 bg-slate-900/20 border border-slate-900 rounded-2xl text-[10px] text-slate-500 space-y-1">
            <span className="font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1"><Info className="w-3 h-3 text-blue-500" /> Interaction Tips:</span>
            <ul className="list-disc pl-4 space-y-0.5">
              <li>Drag nodes to dynamically Pin or customize layout.</li>
              <li>Filter low-impact authors out with min parameter sliders.</li>
              <li>Isolate a community partition by clicking items on the legend.</li>
              <li>Pan using Shift + Left Drag (or Middle Mouse).</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}

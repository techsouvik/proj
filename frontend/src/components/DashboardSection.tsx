"use client";

import React, { useState, useEffect } from "react";

interface SummaryMetrics {
  total_requests: number;
  success_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  error_rate: number;
  cancelled_requests: number;
}

interface ModelShare {
  model: string;
  provider: string;
  requests: number;
  tokens: number;
}

interface TimelinePoint {
  time: string;
  requests: number;
  avg_latency_ms: number;
  tokens: number;
  errors: number;
}

interface SystemError {
  timestamp: string;
  model: string;
  error: string;
}

interface AnalyticsData {
  summary: SummaryMetrics;
  latency_distribution: {
    under_500ms: number;
    between_500ms_1s: number;
    between_1s_2s: number;
    over_2s: number;
  };
  model_shares: ModelShare[];
  throughput_timeline: TimelinePoint[];
  recent_errors: SystemError[];
}

interface DashboardSectionProps {
  backendUrl: string;
  refreshTrigger: number; // Increment to force reload
}

export default function DashboardSection({ backendUrl, refreshTrigger }: DashboardSectionProps) {
  const [metrics, setMetrics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${backendUrl}/api/analytics`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
        setError(null);
      } else {
        throw new Error("Failed to fetch analytics");
      }
    } catch (e: any) {
      console.error(e);
      setError("Unable to connect to the Ingestion pipeline. Verify the Backend is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [backendUrl, refreshTrigger]);

  if (loading && !metrics) {
    return (
      <div className="h-full flex items-center justify-center py-20">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-400">Loading observability telemetry...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 glass-panel rounded-2xl border-red-500/20 max-w-xl mx-auto my-12 text-center space-y-4">
        <div className="p-3 bg-red-500/10 text-red-400 rounded-full w-12 h-12 flex items-center justify-center mx-auto text-glow">
          ✕
        </div>
        <h3 className="text-lg font-bold text-white">Database Ingestion Offline</h3>
        <p className="text-sm text-slate-400 leading-relaxed">{error}</p>
        <button
          onClick={fetchMetrics}
          className="px-5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white text-xs border border-white/10 transition-all"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const summary = metrics?.summary || {
    total_requests: 0,
    success_rate: 100,
    avg_latency_ms: 0,
    total_tokens: 0,
    error_rate: 0,
    cancelled_requests: 0,
  };

  const timeline = metrics?.throughput_timeline || [];
  const modelShares = metrics?.model_shares || [];
  const recentErrors = metrics?.recent_errors || [];

  // --- Draw High Quality Interactive SVG Charts ---
  const generateSvgLinePath = (data: number[], width: number, height: number, minVal: number, maxVal: number) => {
    if (data.length < 2) return "";
    const padding = 20;
    const chartW = width - padding * 2;
    const chartH = height - padding * 2;
    
    const range = maxVal - minVal || 1;
    
    return data
      .map((val, idx) => {
        const x = padding + (idx / (data.length - 1)) * chartW;
        const y = padding + chartH - ((val - minVal) / range) * chartH;
        return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
      })
      .join(" ");
  };

  const generateSvgAreaPath = (data: number[], width: number, height: number, minVal: number, maxVal: number) => {
    const linePath = generateSvgLinePath(data, width, height, minVal, maxVal);
    if (!linePath) return "";
    const padding = 20;
    const chartW = width - padding * 2;
    const chartH = height - padding * 2;
    
    // Append coordinates to close the shape at the bottom
    const startX = padding;
    const endX = padding + chartW;
    const bottomY = padding + chartH;
    
    return `${linePath} L ${endX} ${bottomY} L ${startX} ${bottomY} Z`;
  };

  // 1. Throughput timeline arrays
  const throughputData = timeline.map((p) => p.requests);
  const maxThroughput = Math.max(...throughputData, 3);
  const throughputPath = generateSvgLinePath(throughputData, 500, 150, 0, maxThroughput);
  const throughputAreaPath = generateSvgAreaPath(throughputData, 500, 150, 0, maxThroughput);

  // 2. Latency timeline arrays
  const latencyData = timeline.map((p) => p.avg_latency_ms);
  const maxLatency = Math.max(...latencyData, 1000);
  const latencyPath = generateSvgLinePath(latencyData, 500, 150, 0, maxLatency);
  const latencyAreaPath = generateSvgAreaPath(latencyData, 500, 150, 0, maxLatency);

  return (
    <div className="space-y-8 h-full overflow-y-auto pb-12 pr-1">
      {/* Upper Metrics Highlights grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Inferences */}
        <div className="p-5 glass-panel rounded-2xl flex flex-col justify-between space-y-2">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Inferences</span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-white tracking-tight">{summary.total_requests}</span>
            <span className="text-[10px] text-indigo-400 font-mono">active</span>
          </div>
          <p className="text-[10px] text-slate-500 leading-none">Cumulative logs recorded</p>
        </div>

        {/* Success Rate */}
        <div className="p-5 glass-panel rounded-2xl flex flex-col justify-between space-y-2">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Success Rate</span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-emerald-400 tracking-tight">{summary.success_rate}%</span>
            {summary.cancelled_requests > 0 && (
              <span className="text-[9px] px-1 bg-amber-500/10 text-amber-400 rounded font-semibold">
                {summary.cancelled_requests} cancel
              </span>
            )}
          </div>
          <div className="w-full bg-slate-800 h-1 rounded-full overflow-hidden">
            <div className="bg-emerald-500 h-full rounded-full transition-all duration-500" style={{ width: `${summary.success_rate}%` }} />
          </div>
        </div>

        {/* Average Latency */}
        <div className="p-5 glass-panel rounded-2xl flex flex-col justify-between space-y-2">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Avg Latency</span>
          <div className="flex items-baseline gap-1">
            <span className={`text-3xl font-extrabold tracking-tight ${
              summary.avg_latency_ms < 600 ? "text-emerald-400" : summary.avg_latency_ms < 1500 ? "text-amber-400" : "text-red-400"
            }`}>
              {(summary.avg_latency_ms / 1000).toFixed(2)}
            </span>
            <span className="text-xs font-semibold text-slate-400">sec</span>
          </div>
          <p className="text-[10px] text-slate-500 leading-none">({summary.avg_latency_ms.toFixed(0)} ms average)</p>
        </div>

        {/* Total Tokens */}
        <div className="p-5 glass-panel rounded-2xl flex flex-col justify-between space-y-2">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Token Volume</span>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {summary.total_tokens >= 1000000 
                ? `${(summary.total_tokens / 1000000).toFixed(1)}M`
                : summary.total_tokens >= 1000 
                ? `${(summary.total_tokens / 1000).toFixed(1)}k`
                : summary.total_tokens
              }
            </span>
            <span className="text-[10px] text-slate-400 font-mono">tokens</span>
          </div>
          <p className="text-[10px] text-slate-500 leading-none">Prompt + response output</p>
        </div>
      </div>

      {/* Graphical Timelines */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Throughput Timeline */}
        <div className="p-5 glass-panel rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-300 tracking-wider">Inference Throughput</h3>
            <span className="text-xs font-mono text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded">
              requests / min
            </span>
          </div>
          {timeline.length < 2 ? (
            <div className="h-[150px] flex items-center justify-center text-xs text-slate-500">
              Awaiting further pipeline logs to compile throughput graph...
            </div>
          ) : (
            <div className="relative">
              <svg className="w-full h-[150px]" viewBox="0 0 500 150" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="thruGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                {/* Under Fill Area */}
                {throughputAreaPath && <path d={throughputAreaPath} fill="url(#thruGrad)" />}
                {/* Main Stroke Line */}
                {throughputPath && (
                  <path
                    d={throughputPath}
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}
              </svg>
              {/* Timeline labels bar */}
              <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-2">
                <span>{timeline[0].time}</span>
                <span>{timeline[Math.floor(timeline.length / 2)].time}</span>
                <span>{timeline[timeline.length - 1].time}</span>
              </div>
            </div>
          )}
        </div>

        {/* Latency Speed Timeline */}
        <div className="p-5 glass-panel rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-300 tracking-wider">Average Latency Speed</h3>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
              milliseconds
            </span>
          </div>
          {timeline.length < 2 ? (
            <div className="h-[150px] flex items-center justify-center text-xs text-slate-500">
              Awaiting further pipeline logs to compile latency graph...
            </div>
          ) : (
            <div className="relative">
              <svg className="w-full h-[150px]" viewBox="0 0 500 150" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                {/* Under Fill Area */}
                {latencyAreaPath && <path d={latencyAreaPath} fill="url(#latGrad)" />}
                {/* Main Stroke Line */}
                {latencyPath && (
                  <path
                    d={latencyPath}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}
              </svg>
              {/* Timeline labels bar */}
              <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-2">
                <span>{timeline[0].time}</span>
                <span>{timeline[Math.floor(timeline.length / 2)].time}</span>
                <span>{timeline[timeline.length - 1].time}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Breakdown Panel */}
        <div className="p-5 glass-panel rounded-2xl space-y-4 lg:col-span-1 flex flex-col justify-between">
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-300 tracking-wider">Model Resource Share</h3>
            <p className="text-[10px] text-slate-500">Distribution of calls across nodes</p>
          </div>

          <div className="space-y-4 flex-1 mt-4 overflow-y-auto max-h-[160px] pr-1">
            {modelShares.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-500">No logs found.</div>
            ) : (
              modelShares.map((ms, idx) => {
                const totalReqs = summary.total_requests || 1;
                const percentage = Math.round((ms.requests / totalReqs) * 100);
                return (
                  <div key={idx} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-slate-300 truncate max-w-[150px]">{ms.model}</span>
                      <span className="font-mono text-indigo-400">{percentage}%</span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <div className="bg-indigo-500 h-full rounded-full transition-all duration-300" style={{ width: `${percentage}%` }} />
                    </div>
                    <div className="flex justify-between text-[9px] text-slate-500 font-mono">
                      <span>{ms.requests} requests</span>
                      <span>{ms.tokens} tokens</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Error Diagnostics Logging audit feed */}
        <div className="p-5 glass-panel rounded-2xl space-y-4 lg:col-span-2 flex flex-col">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-slate-300 tracking-wider">Error & Exception Audit Feed</h3>
              <p className="text-[10px] text-slate-500">Live operational system diagnostics</p>
            </div>
            <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold border ${
              summary.error_rate === 0 
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-red-500/10 text-red-400 border-red-500/20"
            }`}>
              SYSTEM ERROR RATE: {summary.error_rate}%
            </span>
          </div>

          <div className="flex-1 mt-3 overflow-y-auto max-h-[160px] pr-1 space-y-2">
            {recentErrors.length === 0 ? (
              <div className="text-center py-10 text-xs text-slate-500 flex flex-col items-center justify-center gap-2">
                <svg className="w-5 h-5 text-emerald-400/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-12 0 9 9 0 0112 0z" />
                </svg>
                <span>Zero service exceptions registered. Operational status healthy.</span>
              </div>
            ) : (
              recentErrors.map((err, idx) => (
                <div key={idx} className="p-3 bg-red-500/5 border border-red-500/10 rounded-xl space-y-1 text-xs">
                  <div className="flex justify-between font-mono text-[9px] text-slate-500">
                    <span>{err.timestamp}</span>
                    <span className="text-red-400 uppercase font-semibold">{err.model}</span>
                  </div>
                  <p className="text-slate-300 font-mono text-[10px] leading-relaxed select-all">
                    {err.error}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

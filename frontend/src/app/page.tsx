"use client";

import React, { useState } from "react";
import ChatSection from "@/components/ChatSection";
import DashboardSection from "@/components/DashboardSection";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"chat" | "dashboard">("chat");
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Retrieve the backend url from env or fallback to local port
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Triggered whenever a chat finishes streaming and telemetries are saved
  const handleLogIngested = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <main className="flex-1 flex flex-col p-4 md:p-8 max-w-7xl mx-auto w-full h-screen min-h-[600px] overflow-hidden">
      {/* Dynamic Glass Header bar */}
      <header className="flex flex-col sm:flex-row items-center justify-between gap-4 pb-6 mb-6 border-b border-white/10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 font-bold text-lg tracking-wider text-glow">
            Æ
          </div>
          <div className="flex flex-col">
            <h1 className="text-xl font-extrabold text-white tracking-wide uppercase">
              Aether <span className="text-indigo-400 font-medium font-sans text-xs lowercase tracking-normal bg-indigo-600/10 border border-indigo-500/20 px-2 py-0.5 rounded-full ml-1.5">v1.0.0</span>
            </h1>
            <p className="text-[10px] text-slate-500 font-mono uppercase tracking-widest leading-none mt-1">
              LLM Real-time Ingestion & Observability
            </p>
          </div>
        </div>

        {/* Tab switcher options */}
        <div className="flex p-1 bg-white/5 border border-white/10 rounded-xl shrink-0">
          <button
            onClick={() => setActiveTab("chat")}
            className={`px-5 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${
              activeTab === "chat"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20 text-glow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Chat Application
          </button>
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`px-5 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${
              activeTab === "dashboard"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20 text-glow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Observability Dashboard
          </button>
        </div>
      </header>

      {/* Main active view panels */}
      <section className="flex-1 overflow-hidden relative">
        <div className={`h-full transition-all duration-300 ${activeTab === "chat" ? "opacity-100 scale-100" : "pointer-events-none opacity-0 scale-95 absolute inset-0"}`}>
          <ChatSection backendUrl={backendUrl} onLogIngested={handleLogIngested} />
        </div>

        <div className={`h-full transition-all duration-300 ${activeTab === "dashboard" ? "opacity-100 scale-100" : "pointer-events-none opacity-0 scale-95 absolute inset-0"}`}>
          <DashboardSection backendUrl={backendUrl} refreshTrigger={refreshTrigger} />
        </div>
      </section>
    </main>
  );
}

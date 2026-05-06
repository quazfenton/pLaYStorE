"use client";

import React, { useState, useEffect } from "react";
import { Search, Star, Download, ShieldCheck, Zap, Globe, Cpu, Box, X, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";

const API_BASE = "http://localhost:8000";

interface AppInfo {
  app_id?: string;
  name: string;
  full_name?: string;
  description: string;
  stars: number;
  language: string;
  url: string;
  trust_score?: number;
}

interface AnalysisData {
  repo_type: string;
  confidence: number;
  build_strategy: string;
  runtime_type: string;
  is_safe: boolean;
  risk_score: number;
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AppInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedApp, setSelectedApp] = useState<AppInfo | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE}/search`, { query });
      setResults(response.data.results);
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-12">
      {/* Header Section */}
      <section className="space-y-6">
        <motion.h1 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-6xl font-black tracking-tighter"
        >
          Discover the <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-600">Open Source</span> Universe.
        </motion.h1>
        <motion.p 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="text-xl text-gray-400 max-w-2xl"
        >
          The next-generation distribution layer for GitHub projects. 
          One-click deployment, sandboxed execution, total transparency.
        </motion.p>
      </section>

      {/* Search Bar Section */}
      <section>
        <form onSubmit={handleSearch} className="relative max-w-2xl">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search GitHub repositories (e.g. 'ripgrep', 'fastapi')..."
            className="w-full h-16 pl-16 pr-6 rounded-2xl glass border-white/10 focus:outline-none focus:border-blue-500/50 transition-all text-lg"
          />
          <Search className="absolute left-6 top-1/2 -translate-y-1/2 text-gray-400" size={24} />
          <button 
            type="submit"
            className="absolute right-4 top-1/2 -translate-y-1/2 px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-xl font-bold transition-colors disabled:opacity-50"
            disabled={loading}
          >
            {loading ? <Loader2 className="animate-spin" /> : "Find"}
          </button>
        </form>
      </section>

      {/* Bento Grid / Results Section */}
      <section>
        <div className="bento-grid">
          <AnimatePresence>
            {results.length > 0 ? (
              results.map((app, i) => (
                <AppCard key={app.full_name || app.name} app={app} index={i} onInstall={() => setSelectedApp(app)} />
              ))
            ) : !loading && (
              <>
                <FeaturedCard 
                  title="Curated Apps" 
                  description="Hand-picked projects optimized for one-click installation."
                  icon={<Star className="text-yellow-400" />}
                  className="md:col-span-2 md:row-span-2"
                />
                <FeaturedCard 
                  title="Secure by Design" 
                  description="All projects run in isolated seccomp sandboxes."
                  icon={<ShieldCheck className="text-green-400" />}
                />
                <FeaturedCard 
                  title="WASM Ready" 
                  description="Native fallback to WebAssembly for absolute portability."
                  icon={<Box className="text-purple-400" />}
                />
                <FeaturedCard 
                  title="High Speed" 
                  description="Delta updates and content-addressable storage for instant loads."
                  icon={<Zap className="text-blue-400" />}
                />
              </>
            )}
          </AnimatePresence>
        </div>
      </section>

      {/* Installation Modal */}
      <AnimatePresence>
        {selectedApp && (
          <InstallModal app={selectedApp} onClose={() => setSelectedApp(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}

const AppCard = ({ app, index, onInstall }: { app: AppInfo; index: number; onInstall: () => void }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.05 }}
      className="glass-card p-6 rounded-3xl flex flex-col justify-between"
    >
      <div>
        <div className="flex justify-between items-start mb-4">
          <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center text-2xl">
            {app.language === 'Python' ? '🐍' : app.language === 'Rust' ? '🦀' : app.language === 'Go' ? '🐹' : '📦'}
          </div>
          <div className="flex gap-2 text-xs font-mono text-gray-400 bg-white/5 px-3 py-1 rounded-full">
            <Star size={12} className="text-yellow-500" />
            {app.stars.toLocaleString()}
          </div>
        </div>
        <h3 className="text-xl font-bold mb-2 truncate">{app.name}</h3>
        <p className="text-sm text-gray-400 line-clamp-3 mb-6">
          {app.description || "No description provided."}
        </p>
      </div>
      
      <div className="flex gap-3">
        <button 
          onClick={onInstall}
          className="flex-1 py-3 bg-white text-black font-bold rounded-xl hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
        >
          <Download size={18} />
          Install
        </button>
        <a 
          href={app.url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors"
        >
          <Globe size={18} />
        </a>
      </div>
    </motion.div>
  );
};

const FeaturedCard = ({ title, description, icon, className }: { title: string; description: string; icon: React.ReactNode; className?: string }) => {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass-card p-8 rounded-3xl flex flex-col justify-center gap-4 ${className}`}
    >
      <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center scale-125 mb-4">
        {icon}
      </div>
      <h2 className="text-3xl font-black tracking-tight">{title}</h2>
      <p className="text-gray-400 text-lg leading-relaxed">
        {description}
      </p>
    </motion.div>
  );
};

const InstallModal = ({ app, onClose }: { app: AppInfo; onClose: () => void }) => {
  const [step, setStep] = useState<'analyze' | 'install' | 'complete' | 'error'>('analyze');
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [installStatus, setInstallStatus] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (step === 'analyze') {
      const [owner, name] = (app.full_name || "").split("/");
      axios.get(`${API_BASE}/analyze/${owner}/${name}`)
        .then(res => {
          setAnalysis(res.data);
        })
        .catch(err => {
          setError("Analysis failed: " + err.message);
          setStep('error');
        });
    }
  }, [app, step]);

  const startInstall = async () => {
    setStep('install');
    try {
      const res = await axios.post(`${API_BASE}/install`, { 
        github_repo: app.full_name,
        user_preferences: { allow_wasm: true }
      });
      const workflowId = res.data.workflow_id;
      
      // Poll for status
      const interval = setInterval(async () => {
        const statusRes = await axios.get(`${API_BASE}/workflow/${workflowId}`);
        setInstallStatus(statusRes.data);
        if (statusRes.data.status === 'complete') {
          clearInterval(interval);
          setStep('complete');
        } else if (statusRes.data.status === 'failed') {
          clearInterval(interval);
          setError(statusRes.data.error || "Installation failed");
          setStep('error');
        }
      }, 2000);
    } catch (err: any) {
      setError(err.message);
      setStep('error');
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
      />
      <motion.div 
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 20 }}
        className="relative w-full max-w-xl glass p-8 rounded-[40px] shadow-2xl border border-white/10"
      >
        <button onClick={onClose} className="absolute right-6 top-6 p-2 hover:bg-white/5 rounded-full transition-colors">
          <X size={20} />
        </button>

        <div className="space-y-8">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-blue-500/20 flex items-center justify-center text-3xl">
              {app.language === 'Python' ? '🐍' : app.language === 'Rust' ? '🦀' : app.language === 'Go' ? '🐹' : '📦'}
            </div>
            <div>
              <h2 className="text-2xl font-bold">{app.name}</h2>
              <p className="text-gray-400 text-sm">{app.full_name}</p>
            </div>
          </div>

          <div className="min-h-[200px] flex flex-col justify-center">
            {step === 'analyze' && (
              <div className="space-y-6">
                {!analysis ? (
                  <div className="flex flex-col items-center gap-4 py-8">
                    <Loader2 className="animate-spin text-blue-500" size={48} />
                    <p className="text-lg font-medium animate-pulse">Analyzing repository architecture...</p>
                  </div>
                ) : (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                        <p className="text-xs text-gray-500 uppercase font-bold mb-1">Type</p>
                        <p className="text-lg font-bold capitalize">{analysis.repo_type.replace('_', ' ')}</p>
                      </div>
                      <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                        <p className="text-xs text-gray-500 uppercase font-bold mb-1">Safety Score</p>
                        <p className={`text-lg font-bold ${analysis.is_safe ? 'text-green-400' : 'text-red-400'}`}>
                          {Math.round((1 - analysis.risk_score) * 100)}%
                        </p>
                      </div>
                    </div>
                    <div className="p-4 rounded-2xl bg-blue-500/10 border border-blue-500/20">
                      <p className="text-sm text-blue-300 mb-2 font-medium flex items-center gap-2">
                        <Zap size={16} /> Suggested Strategy
                      </p>
                      <p className="text-white">Build via <span className="font-bold text-blue-400 uppercase">{analysis.build_strategy}</span> into a <span className="font-bold text-purple-400 uppercase">{analysis.runtime_type}</span> capsule.</p>
                    </div>
                    <button 
                      onClick={startInstall}
                      className="w-full py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-2xl transition-all shadow-lg shadow-blue-500/20"
                    >
                      Execute One-Click Install
                    </button>
                  </motion.div>
                )}
              </div>
            )}

            {step === 'install' && (
              <div className="flex flex-col items-center gap-6 py-8">
                <div className="relative">
                  <Loader2 className="animate-spin text-blue-500" size={64} />
                  <div className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                    {installStatus?.progress || 0}%
                  </div>
                </div>
                <div className="text-center space-y-2">
                  <p className="text-xl font-bold">Installing Application</p>
                  <p className="text-gray-400">{installStatus?.status || "Starting workflow..."}</p>
                </div>
                <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${installStatus?.progress || 10}%` }}
                    className="h-full bg-blue-500"
                  />
                </div>
              </div>
            )}

            {step === 'complete' && (
              <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex flex-col items-center gap-6 py-8 text-center">
                <div className="w-20 h-20 rounded-full bg-green-500/20 flex items-center justify-center text-green-500">
                  <CheckCircle2 size={48} />
                </div>
                <div className="space-y-2">
                  <p className="text-2xl font-bold">Installation Successful</p>
                  <p className="text-gray-400">{app.name} is now ready to run in your sandbox.</p>
                </div>
                <button 
                  onClick={onClose}
                  className="px-8 py-3 bg-white text-black font-bold rounded-xl hover:bg-gray-200 transition-all"
                >
                  Launch Application
                </button>
              </motion.div>
            )}

            {step === 'error' && (
              <div className="flex flex-col items-center gap-6 py-8 text-center">
                <div className="w-20 h-20 rounded-full bg-red-500/20 flex items-center justify-center text-red-500">
                  <AlertCircle size={48} />
                </div>
                <div className="space-y-2">
                  <p className="text-2xl font-bold">Workflow Failed</p>
                  <p className="text-red-400/80 text-sm max-w-xs">{error}</p>
                </div>
                <button 
                  onClick={() => setStep('analyze')}
                  className="px-8 py-3 bg-white/10 text-white font-bold rounded-xl hover:bg-white/20 transition-all"
                >
                  Retry Analysis
                </button>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
};

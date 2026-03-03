"use client";

import React, { useState, useEffect } from "react";
import { Box, Play, Trash2, Shield, externalLink } from "lucide-react";
import { motion } from "framer-motion";
import axios from "axios";

const API_BASE = "http://localhost:8000";

export default function InstalledPage() {
  const [apps, setApps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API_BASE}/apps`)
      .then(res => {
        // Map history to "installed" apps
        const installed = res.data.apps.filter((app: any) => app.status === 'complete');
        setApps(installed);
      })
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-12">
      <section>
        <h1 className="text-5xl font-black tracking-tighter mb-4">Your <span className="text-blue-500">Vault</span>.</h1>
        <p className="text-gray-400 text-lg">Manage your sandboxed applications and execution environments.</p>
      </section>

      <section>
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-48 glass-card animate-pulse rounded-3xl" />
            ))}
          </div>
        ) : apps.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {apps.map((app, i) => (
              <InstalledCard key={app.id} app={app} index={i} />
            ))}
          </div>
        ) : (
          <div className="glass-card p-12 rounded-[40px] text-center space-y-4">
            <div className="w-20 h-20 bg-white/5 rounded-3xl flex items-center justify-center mx-auto mb-6">
              <Box size={40} className="text-gray-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-400">No applications installed yet.</h2>
            <p className="text-gray-500">Explore the universe to find your first project.</p>
          </div>
        )}
      </section>
    </div>
  );
}

const InstalledCard = ({ app, index }: { app: any; index: number }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="glass-card p-8 rounded-[32px] group"
    >
      <div className="flex justify-between items-start mb-6">
        <div className="w-14 h-14 rounded-2xl bg-blue-500/10 flex items-center justify-center text-2xl group-hover:bg-blue-500/20 transition-colors">
          📦
        </div>
        <div className="flex gap-2">
          <span className="px-3 py-1 bg-green-500/10 text-green-500 text-[10px] font-bold uppercase tracking-wider rounded-full border border-green-500/20">
            Secure
          </span>
        </div>
      </div>

      <h3 className="text-xl font-bold mb-1">{app.repo.split('/')[1]}</h3>
      <p className="text-xs text-gray-500 mb-8 font-mono">{app.repo}</p>

      <div className="flex gap-3 mt-auto">
        <button className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/10">
          <Play size={16} fill="currentColor" />
          Run
        </button>
        <button className="p-3 bg-white/5 hover:bg-red-500/20 hover:text-red-500 rounded-xl transition-all">
          <Trash2 size={18} />
        </button>
      </div>
    </motion.div>
  );
};

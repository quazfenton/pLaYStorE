"use client";

import React from "react";
import Link from "next/link";
import { LayoutGrid, Download, Compass, Settings, Github } from "lucide-react";
import { motion } from "framer-motion";

const Navbar = () => {
  return (
    <nav className="fixed left-0 top-0 h-full w-20 flex flex-col items-center py-8 z-50 glass border-r border-white/10">
      <div className="mb-12">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <span className="font-bold text-xl text-white">P</span>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-8">
        <NavItem icon={<Compass size={24} />} label="Explore" active href="/" />
        <NavItem icon={<LayoutGrid size={24} />} label="Catalog" href="/catalog" />
        <NavItem icon={<Download size={24} />} label="Installed" href="/installed" />
        <NavItem icon={<Github size={24} />} label="GitHub" href="/github" />
      </div>

      <div className="mt-auto">
        <NavItem icon={<Settings size={24} />} label="Settings" href="/settings" />
      </div>
    </nav>
  );
};

const NavItem = ({ icon, label, active = false, href }: { icon: React.ReactNode; label: string; active?: boolean; href: string }) => {
  return (
    <Link href={href} className="group relative">
      <div className={`p-3 rounded-xl transition-all duration-300 ${active ? 'bg-white/10 text-blue-400' : 'text-gray-400 hover:bg-white/5 hover:text-white'}`}>
        {icon}
      </div>
      <div className="absolute left-full ml-4 px-2 py-1 rounded bg-gray-800 text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
        {label}
      </div>
      {active && (
        <motion.div 
          layoutId="active-indicator"
          className="absolute left-0 top-0 w-1 h-full bg-blue-500 rounded-r-full shadow-[0_0_8px_rgba(59,130,246,0.5)]"
        />
      )}
    </Link>
  );
};

export default Navbar;

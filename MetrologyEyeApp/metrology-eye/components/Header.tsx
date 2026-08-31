"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { HealthResponse } from "@/lib/types";

export function Header() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadHealth() {
      try {
        const res = await fetch("http://localhost:8000/health", {
          signal: AbortSignal.timeout(1500),
        });
        if (res.ok && mounted) {
          const data = await res.json();
          setHealth(data);
        }
      } catch {
        if (mounted) setHealth(null);
      }
    }
    loadHealth();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <header className="w-full bg-white dark:bg-zinc-950 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-13 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Link href="/" className="flex items-center space-x-2 font-semibold tracking-tight text-sm text-zinc-900 dark:text-zinc-100">
            <span className="w-2 h-2 bg-zinc-900 dark:bg-zinc-100 rounded-full" />
            <span>MetrologyEye</span>
          </Link>
          <span className="text-zinc-300 dark:text-zinc-700">/</span>
          <span className="text-xs text-zinc-500 font-mono">
            {health ? "Live Backend" : "Demo Ready"}
          </span>
        </div>

        <nav className="flex items-center space-x-4 text-xs font-medium">
          <Link
            href="/"
            className="text-zinc-600 hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
          >
            Upload
          </Link>
        </nav>
      </div>
    </header>
  );
}

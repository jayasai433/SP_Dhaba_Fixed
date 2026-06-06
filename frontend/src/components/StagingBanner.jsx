/**
 * StagingBanner — always visible, shows which environment and DB
 * the frontend is currently connected to.
 *
 * In production: subtle grey bar — unobtrusive but confirmable
 * In staging:    bold yellow bar — impossible to miss
 *
 * Calls /api/health on mount to get the real DB name from the backend.
 * This is the ground truth — if DB name says "sp_dhaba_staging" you
 * are 100% not touching production data.
 */

import { useEffect, useState } from "react";
import { Database, CheckCircle2, AlertTriangle } from "lucide-react";
import api from "@/lib/api";

export default function StagingBanner() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    api.get("/health")
      .then(({ data }) => setInfo(data))
      .catch(() => setInfo({ status: "error", environment: "unknown", db_name: "unknown" }));
  }, []);

  if (!info) return null;

  const isStaging = info.environment === "staging";
  const isProd    = info.environment === "production";

  if (isProd) {
    // Production — small subtle bar, confirms you're on prod
    return (
      <div className="w-full bg-slate-100 border-b border-slate-200 text-slate-500 text-[11px] flex items-center justify-center gap-2 py-1 px-4">
        <Database size={11} />
        <span>
          <span className="font-semibold text-slate-700">Production</span>
          {" · "}DB: <span className="font-mono font-semibold text-slate-700">{info.db_name}</span>
        </span>
        <CheckCircle2 size={11} className="text-green-500" />
      </div>
    );
  }

  if (isStaging) {
    // Staging — bold yellow, impossible to miss
    return (
      <div className="w-full bg-yellow-400 border-b border-yellow-500 text-yellow-900 text-xs font-semibold flex items-center justify-center gap-2 py-1.5 px-4">
        <AlertTriangle size={13} />
        <span>
          STAGING ENVIRONMENT — DB:{" "}
          <span className="font-mono bg-yellow-300 px-1.5 py-0.5 rounded">
            {info.db_name}
          </span>
          {" "}— Test data only. Do not enter real transactions.
        </span>
      </div>
    );
  }

  // Unknown environment — show warning
  return (
    <div className="w-full bg-red-100 border-b border-red-300 text-red-800 text-xs font-semibold flex items-center justify-center gap-2 py-1.5 px-4">
      <AlertTriangle size={13} />
      Unknown environment — DB: <span className="font-mono">{info.db_name}</span>
      {" "}— Check your Railway environment variables.
    </div>
  );
}

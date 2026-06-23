/**
 * DailyDigestCard — Groq morning briefing on Dashboard.
 * Cached server-side until midnight IST — one Groq call per day.
 * Admin + Viewer only. Hides silently if Groq unavailable.
 */
import { useEffect, useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Sparkles, RefreshCw, Coffee } from "lucide-react";
import api from "@/lib/api";
import logger from "@/lib/logger";

export default function DailyDigestCard() {
  const [insight, setInsight] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cached, setCached]   = useState(false);
  const [date, setDate]       = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/daily-digest");
      if (data.insight) {
        setInsight(data.insight);
        setCached(data.cached);
        setDate(data.date);
      }
    } catch (err) {
      logger.error("Daily digest failed:", err);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  if (!loading && !insight) return null;

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm bg-gradient-to-br from-amber-50 to-orange-50">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-orange-700">
            <Coffee size={16} />
            <span className="text-xs font-semibold uppercase tracking-wider">
              Morning Briefing
            </span>
            {date && (
              <span className="text-xs text-orange-400 font-normal">
                · {new Date(date + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
              </span>
            )}
          </div>
          <button onClick={load} title="Refresh"
            className="text-orange-400 hover:text-orange-600 transition-colors">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>

        {loading ? (
          <div className="space-y-2">
            <div className="h-4 bg-orange-100 rounded animate-pulse w-full" />
            <div className="h-4 bg-orange-100 rounded animate-pulse w-4/5" />
            <div className="h-4 bg-orange-100 rounded animate-pulse w-3/5" />
          </div>
        ) : (
          <>
            <p className="text-slate-700 text-sm leading-relaxed">{insight}</p>
            <div className="flex items-center gap-1 mt-3">
              <Sparkles size={10} className="text-orange-400" />
              <p className="text-xs text-slate-400">
                {cached ? "Cached · " : ""}Powered by Groq AI · Updates daily
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

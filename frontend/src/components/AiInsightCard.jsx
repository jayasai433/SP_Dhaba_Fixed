/**
 * AiInsightCard — Groq-powered dashboard insight
 * Admin + Viewer only. Hides silently if Groq is down or key missing.
 */
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Sparkles, RefreshCw } from "lucide-react";
import api from "@/lib/api";
import logger from "@/lib/logger";

export default function AiInsightCard() {
  const [insight, setInsight] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cached, setCached] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/ai-insight");
      if (data.insight) {
        setInsight(data.insight);
        setCached(data.cached);
      }
    } catch (err) {
      logger.error("AI insight failed:", err);
      // Fail silently — card just won't show
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Don't render anything if no insight (Groq down or key missing)
  if (!loading && !insight) return null;

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm bg-gradient-to-br from-orange-50 to-amber-50">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-orange-700">
            <Sparkles size={16} />
            <span className="text-xs font-semibold uppercase tracking-wider">
              SP Dhaba Intelligence
            </span>
          </div>
          <button
            onClick={load}
            title="Refresh insight"
            className="text-orange-400 hover:text-orange-600 transition-colors"
          >
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
            <p className="text-xs text-slate-400 mt-3">
              {cached ? "Cached · " : ""}Powered by Groq AI
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * SmartReorderCard — Groq-powered reorder advice on Dashboard.
 * Admin + Viewer only. Hides silently if Groq unavailable.
 * Cache: 1 hour server-side — no excessive API calls.
 */
import { Sparkles, RefreshCw, ShoppingCart } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useSmartReorder } from "@/hooks/useConsumption";
import api from "@/lib/api";
import logger from "@/lib/logger";
import { useState } from "react";

export default function SmartReorderCard() {
  const { insight, loading, cached, reload } = useSmartReorder();
  const [refreshing, setRefreshing] = useState(false);

  const forceRefresh = async () => {
    setRefreshing(true);
    try {
      await api.post("/smart-reorder/refresh");
      await reload();
    } catch (err) {
      logger.error("Smart reorder refresh failed:", err);
    } finally {
      setRefreshing(false);
    }
  };

  // Always render — show message if no insight

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm bg-gradient-to-br from-orange-50 to-amber-50">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-orange-700">
            <ShoppingCart size={16} />
            <span className="text-xs font-semibold uppercase tracking-wider">
              Smart Reorder Advice
            </span>
          </div>
          <button
            onClick={forceRefresh}
            title={cached ? "Cached — click to refresh" : "Refresh"}
            className="text-orange-400 hover:text-orange-600 transition-colors"
          >
            <RefreshCw size={14} className={(loading || refreshing) ? "animate-spin" : ""} />
          </button>
        </div>

        {loading ? (
          <div className="space-y-2">
            <div className="h-4 bg-orange-100 rounded animate-pulse w-full" />
            <div className="h-4 bg-orange-100 rounded animate-pulse w-4/5" />
            <div className="h-4 bg-orange-100 rounded animate-pulse w-3/5" />
          </div>
        ) : insight ? (
          <>
            <p className="text-slate-700 text-sm leading-relaxed">{insight}</p>
            <div className="flex items-center gap-1 mt-3">
              <Sparkles size={10} className="text-orange-400" />
              <p className="text-xs text-slate-400">
                {cached ? "Cached · " : ""}Powered by Groq AI
              </p>
            </div>
          </>
        ) : (
          <p className="text-sm text-slate-500 italic">
            Enter at least 2 purchases per item to get smart reorder advice. Groq will analyse your consumption patterns and suggest when to reorder.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

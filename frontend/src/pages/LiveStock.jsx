/**
 * Stock Tracker — shows estimated stock remaining based on purchase history.
 * No manual counting needed — calculated from purchase dates + quantities.
 */
import { useEffect, useState, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Package2, AlertOctagon, Flame, Clock, CheckCircle2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";
import logger from "@/lib/logger";

// Status config based on consumption tracker
const STATUS_META = {
  overdue:           { label: "Reorder Now",  dot: "bg-red-600",    card: "border-red-200 bg-red-50",    icon: AlertOctagon, iconColor: "text-red-600" },
  urgent:            { label: "Reorder Today", dot: "bg-orange-500", card: "border-orange-200 bg-orange-50", icon: Flame,        iconColor: "text-orange-600" },
  soon:              { label: "Reorder Soon",  dot: "bg-amber-500",  card: "border-amber-200 bg-amber-50",  icon: Clock,        iconColor: "text-amber-600" },
  ok:                { label: "OK",            dot: "bg-green-500",  card: "border-green-200 bg-green-50",  icon: CheckCircle2, iconColor: "text-green-600" },
  unknown:           { label: "Unknown",       dot: "bg-slate-400",  card: "border-slate-200 bg-slate-50",  icon: Package2,     iconColor: "text-slate-400" },
  insufficient_data: { label: "No Data",       dot: "bg-slate-300",  card: "border-slate-200 bg-white",     icon: Package2,     iconColor: "text-slate-300" },
};

const STATUS_ORDER = { overdue: 0, urgent: 1, soon: 2, ok: 3, unknown: 4, insufficient_data: 5 };

export default function LiveStock() {
  const [rates, setRates]   = useState(null);
  const [error, setError]   = useState(false);
  const [q, setQ]           = useState("");
  const [statusF, setStatusF] = useState("all");

  const load = useCallback(() => {
    api.get("/consumption-rates")
      .then(({ data }) => setRates(data.rates || []))
      .catch((err) => { logger.error("Stock tracker load failed:", err); setError(true); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    if (!rates) return [];
    return rates
      .filter((r) => {
        const matchQ      = !q || r.item_name.toLowerCase().includes(q.toLowerCase());
        const matchStatus = statusF === "all" || r.status === statusF;
        return matchQ && matchStatus;
      })
      .sort((a, b) =>
        (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9)
      );
  }, [rates, q, statusF]);

  if (error) return (
    <div className="text-center py-20 text-slate-500">
      <Package2 className="mx-auto mb-3 text-orange-300" size={40} />
      <p className="font-medium">Could not load stock data</p>
      <button onClick={load} className="mt-3 text-sm text-orange-600 underline">Try again</button>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-up" data-testid="live-stock-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Inventory</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Stock Tracker</h1>
        <p className="text-sm text-slate-500 mt-1">
          Estimated remaining stock based on purchase history — no manual counting needed.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-3 text-slate-400" />
          <Input data-testid="stock-search" value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search items..." className="pl-9 h-11 bg-white" />
        </div>
        <Select value={statusF} onValueChange={setStatusF}>
          <SelectTrigger className="h-11 w-full sm:w-44 bg-white">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="overdue">Reorder Now</SelectItem>
            <SelectItem value="urgent">Reorder Today</SelectItem>
            <SelectItem value="soon">Reorder Soon</SelectItem>
            <SelectItem value="ok">OK</SelectItem>
            <SelectItem value="insufficient_data">No Data Yet</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Grid */}
      {rates === null ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {SKELETON_KEYS.slice(0, 8).map((k) => (
            <Skeleton key={k} className="h-32 rounded-2xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Package2 className="mx-auto mb-3 text-orange-300" size={40} />
          <p className="font-medium">No items found</p>
          <p className="text-sm mt-1">Try a different search or filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3"
          data-testid="stock-grid">
          {filtered.map((r) => {
            const meta = STATUS_META[r.status] || STATUS_META.unknown;
            const Icon = meta.icon;
            return (
              <Link to={`/purchases?item=${r.item_id}`} key={r.item_id}
                data-testid={`stock-card-${r.item_id}`}
                className={`p-4 rounded-2xl border transition-shadow hover:shadow-md ${meta.card}`}>

                {/* Item name + status */}
                <div className="flex items-start justify-between gap-1 mb-2">
                  <div className="font-display font-semibold text-sm text-slate-900 leading-tight">
                    {r.item_name}
                  </div>
                  <Icon size={14} className={`shrink-0 mt-0.5 ${meta.iconColor}`} />
                </div>

                {/* Estimated remaining */}
                {r.est_remaining !== undefined && r.est_remaining !== null ? (
                  <div className="font-display font-bold text-2xl tabular-nums text-slate-900">
                    {r.est_remaining <= 0 ? "0" : r.est_remaining}
                    <span className="text-sm font-normal text-slate-500 ml-1">{r.unit}</span>
                  </div>
                ) : (
                  <div className="text-xs text-slate-400 italic mt-1">
                    Need 2+ purchases
                  </div>
                )}

                {/* Days left */}
                {r.est_days_remaining !== null && r.est_days_remaining !== undefined && (
                  <div className="text-xs text-slate-500 mt-1">
                    ~{r.est_days_remaining > 0 ? r.est_days_remaining : 0} days left
                  </div>
                )}

                {/* Daily rate */}
                {r.daily_rate && (
                  <div className="text-xs text-slate-400 mt-0.5">
                    {r.daily_rate} {r.unit}/day avg
                  </div>
                )}

                {/* Status badge */}
                <div className="mt-2">
                  <span className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide ${meta.iconColor}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                    {meta.label}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

import { useEffect, useState, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Search, Package2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";

const STATUS_META = {
  in: { label: "In Stock", color: "bg-[#E8F5E9] border-[#2E7D32]/20 text-[#2E7D32]", dot: "bg-[#2E7D32]" },
  low: { label: "Low Stock", color: "bg-[#FFFDE7] border-[#F57F17]/30 text-[#A35E00]", dot: "bg-[#F57F17]" },
  out: { label: "Out of Stock", color: "bg-[#FFEBEE] border-[#C62828]/20 text-[#C62828]", dot: "bg-[#C62828]" },
};

export default function LiveStock() {
  const [stock, setStock] = useState(null);
  const [error, setError] = useState(false);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [status, setStatus] = useState("all");

  const load = useCallback(() => api.get("/stock").then(({ data }) => setStock(data)).catch(() => setError(true)), []);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);

  const categories = useMemo(() => {
    if (!stock) return [];
    return Array.from(new Set(stock.map((s) => s.category))).sort();
  }, [stock]);

  const filtered = useMemo(() => {
    if (!stock) return [];
    return stock.filter((s) => s.is_active)
      .filter((s) => !q || s.name.toLowerCase().includes(q.toLowerCase()))
      .filter((s) => cat === "all" || s.category === cat)
      .filter((s) => status === "all" || s.status === status);
  }, [stock, q, cat, status]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <div className="text-4xl mb-3">📦</div>
        <p className="font-medium">Could not load stock data</p>
        <p className="text-sm mt-1">Check your connection and refresh the page</p>
      </div>
    );
  }

  if (!stock) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {SKELETON_KEYS.slice(0, 8).map((k) => <Skeleton key={k} className="h-28 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up" data-testid="live-stock-page">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Inventory</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Live Stock</h1>
          <p className="text-slate-600 text-sm mt-1">Auto-refreshes every 60 seconds</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <Input data-testid="stock-search" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search items..." className="pl-9 h-11 w-full sm:w-56 rounded-lg bg-white" />
          </div>
          <Select value={cat} onValueChange={setCat}>
            <SelectTrigger data-testid="stock-filter-category" className="h-11 w-full sm:w-44 rounded-lg bg-white"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger data-testid="stock-filter-status" className="h-11 w-full sm:w-36 rounded-lg bg-white"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="in">In Stock</SelectItem>
              <SelectItem value="low">Low Stock</SelectItem>
              <SelectItem value="out">Out of Stock</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <Card className="rounded-2xl border-dashed border-2 border-orange-200">
          <CardContent className="p-10 text-center">
            <Package2 className="mx-auto text-orange-300" size={48} />
            <p className="mt-3 text-slate-600">No items match your filters.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="stock-grid">
          {filtered.map((s) => {
            const meta = STATUS_META[s.status];
            return (
              <Link to={`/purchases?item=${s.item_id}`} key={s.item_id}
                data-testid={`stock-card-${s.item_id}`}
                className={cn("p-4 rounded-2xl border shadow-sm hover:shadow-md transition-all", meta.color)}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[11px] uppercase tracking-wider opacity-80">{s.category}</div>
                    <div className="font-display font-semibold text-base text-slate-900 truncate">{s.name}</div>
                  </div>
                  <div className={cn("h-2.5 w-2.5 rounded-full mt-1.5 shrink-0", meta.dot)} />
                </div>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className="font-display text-2xl font-bold tabular-nums text-slate-900">{s.qty_left}</span>
                  <span className="text-xs text-slate-600">{s.unit}</span>
                </div>
                <div className="mt-1 text-[11px] flex items-center justify-between">
                  {/* Reorder level hidden until v2.0 alerts feature is re-enabled */}
                  <Badge className={cn("rounded-full text-[10px] py-0", meta.color, "border")}>{meta.label}</Badge>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

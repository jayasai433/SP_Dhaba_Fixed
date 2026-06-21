import { useEffect, useState, useCallback } from "react";
import logger from "@/lib/logger";
import api from "@/lib/api";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  IndianRupee, TrendingUp, ShoppingBag, AlertTriangle, PackageX, CalendarDays,
  Wallet, TrendingDown, Scale, Filter
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip,
  PieChart, Pie, Cell, CartesianGrid
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";
import { cn } from "@/lib/utils";

const STATUS_COLORS = { in: "#2E7D32", low: "#F57F17", out: "#C62828" };

// ── Date range helpers ────────────────────────────────────────────────────────
function getRange(period) {
  const today = todayIST();
  const d     = new Date(today + "T00:00:00");
  switch (period) {
    case "day":   return { start: today, end: today, label: "Today" };
    case "week": {
      const s = new Date(d); s.setDate(d.getDate() - 6);
      return { start: s.toISOString().slice(0, 10), end: today, label: "This Week" };
    }
    case "month": {
      const s = new Date(d.getFullYear(), d.getMonth(), 1);
      return { start: s.toISOString().slice(0, 10), end: today, label: "This Month" };
    }
    default: return null; // custom
  }
}

// ── KPI card — auto-shrinks font for long numbers ────────────────────────────
function KPI({ icon: Icon, label, value, hint, color = "orange", testid }) {
  const palette = {
    orange: "bg-orange-50 text-orange-600",
    green:  "bg-green-50 text-green-700",
    amber:  "bg-amber-50 text-amber-700",
    red:    "bg-red-50 text-red-700",
    slate:  "bg-slate-100 text-slate-700",
  }[color];

  // Auto-shrink font size based on value length
  const valStr  = String(value);
  const fontSize = valStr.length > 10 ? "text-lg" : valStr.length > 7 ? "text-xl" : "text-2xl";

  // Map hint → badge styling. "Break-Even" is a new neutral state.
  const hintStyle = hint === "Profit"     ? "bg-green-100 text-green-700"
                  : hint === "Loss"       ? "bg-red-100 text-red-700"
                  : hint === "Break-Even" ? "bg-slate-100 text-slate-600"
                  : null;

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid={testid}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className={`h-9 w-9 rounded-xl flex items-center justify-center ${palette}`}>
            <Icon size={18} />
          </div>
          {hint && hintStyle && (
            <span
              data-testid={`${testid}-hint`}
              className={cn(
                "text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded",
                hintStyle
              )}
            >{hint}</span>
          )}
        </div>
        <div className="mt-3">
          <div className="text-[10px] font-semibold tracking-widest uppercase text-slate-500 truncate">{label}</div>
          <div className={cn("font-display font-bold text-slate-900 mt-1 tabular-nums leading-tight", fontSize)}>
            {value}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Chart axis formatters ─────────────────────────────────────────────────────
const fmtTick = (v) => {
  const abs  = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 10000000) return `${sign}₹${(abs / 10000000).toFixed(1)}Cr`;
  if (abs >= 100000)   return `${sign}₹${(abs / 100000).toFixed(1)}L`;
  if (abs >= 1000)     return `${sign}₹${(abs / 1000).toFixed(0)}k`;
  return `${sign}₹${abs}`;
};

const fmtXDate = (d) => {
  const dt = new Date(d + "T00:00:00");
  return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
};

// ── Custom dot — only shown for non-zero values ───────────────────────────────
const SmartDot = (props) => {
  const { cx, cy, value } = props;
  if (!value || value === 0) return null;
  return <circle key={`d-${cx}`} cx={cx} cy={cy} r={3} fill="#E65C00" stroke="#fff" strokeWidth={1} />;
};

export default function Dashboard() {
  const [data,      setData]      = useState(null);
  const [filtered,  setFiltered]  = useState(null);
  const [error,     setError]     = useState(false);
  const [period,    setPeriod]    = useState("day");
  const [custom,    setCustom]    = useState({ start: "", end: "" });
  const [loading,   setLoading]   = useState(false);

  // Fetch base dashboard (always all-time for stock health + trend)
  useEffect(() => {
    const fetch = () =>
      api.get("/dashboard")
        .then(({ data: d }) => setData(d))
        .catch(() => setError(true));
    fetch();
    const t = setInterval(fetch, 60000);
    return () => clearInterval(t);
  }, []);

  // Fetch filtered KPI data when period changes
  const fetchFiltered = useCallback(async (p, cust) => {
    setLoading(true);
    try {
      const range = p === "custom" ? cust : getRange(p);
      if (!range?.start || !range?.end) { setLoading(false); return; }

      const [salesRes, expRes, purRes, pnlRes] = await Promise.all([
        api.get("/sales",    { params: { start: range.start, end: range.end } }),
        api.get("/expenses", { params: { start: range.start, end: range.end } }),
        api.get("/purchases",{ params: { start: range.start, end: range.end } }),
        api.get("/pnl",      { params: { period: p === "custom" ? "custom" : p,
                                          start: range.start, end: range.end } }),
      ]);

      const sales    = salesRes.data.reduce((s, r) => s + r.total_amount, 0);
      const expenses = expRes.data
        .filter(e => !e.is_void)
        .reduce((s, e) => s + e.amount, 0);
      const purchases = purRes.data
        .filter(p => !p.is_void)
        .reduce((s, p) => s + p.total_cost, 0);
      const pnl = pnlRes.data;

      setFiltered({
        sales,
        expenses,
        purchases,
        net: pnl?.net_profit ?? (sales - expenses - purchases),
        range,
      });
    } catch (e) {
      logger.error("Filter fetch failed:", e);
    } finally {
      setLoading(false);
    }
  // api is a module-level stable object; setter fns from useState are stable — empty deps is correct
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchFiltered(period, custom);
  // custom is intentionally excluded: fetchFiltered receives it as an arg,
  // so adding it here would double-fire on every keystroke in the custom date inputs
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period, fetchFiltered]);

  if (error) return (
    <div className="flex flex-col items-center justify-center py-20 text-slate-500">
      <AlertTriangle size={40} className="text-orange-400 mb-3" />
      <p className="font-medium">Could not load dashboard</p>
    </div>
  );

  if (!data) return (
    <div className="space-y-6" data-testid="dashboard-loading">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {SKELETON_KEYS.slice(0, 8).map((k) => <Skeleton key={k} className="h-28 rounded-2xl" />)}
      </div>
    </div>
  );

  const range     = period === "custom" ? custom : getRange(period);
  const rangeLabel = period === "custom" ? "Custom Range" : range?.label ?? "Today";

  const pieData = [
    { name: "In Stock",    value: data.stock_health.in,  color: STATUS_COLORS.in  },
    { name: "Low Stock",   value: data.stock_health.low, color: STATUS_COLORS.low },
    { name: "Out of Stock",value: data.stock_health.out, color: STATUS_COLORS.out },
  ];

  const maxCat = Math.max(1, ...data.category_spend.map((c) => c.amount));
  const maxExp = Math.max(1, ...(data.expense_category_spend || []).map((x) => x.amount));

  // KPI values — use filtered if available
  const kpiSales    = filtered?.sales     ?? data.today_sales;
  const kpiExp      = filtered?.expenses  ?? data.today_expenses;
  const kpiPur      = filtered?.purchases ?? 0;
  const kpiNet      = filtered?.net       ?? data.today_pnl;
  const isProfit    = kpiNet > 0;
  const isLoss      = kpiNet < 0;
  const periodHasTxns   = (kpiSales + kpiExp + kpiPur) > 0;
  const periodPnlHint   = isProfit ? "Profit" : isLoss ? "Loss" : periodHasTxns ? "Break-Even" : null;

  // Overall (all-time) P&L hint
  const allTimeHasTxns  = (data.total_sales + data.total_spent) > 0;
  const allTimePnlHint  = data.profit > 0 ? "Profit"
                        : data.profit < 0 ? "Loss"
                        : allTimeHasTxns  ? "Break-Even" : null;

  return (
    <div className="space-y-6 animate-fade-up" data-testid="dashboard-page">

      {/* Header + filter */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Overview</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">Dashboard</h1>
          <p className="text-slate-600 text-sm mt-1">{fmtDate(todayIST())} · All amounts in INR (₹)</p>
        </div>

        {/* Period filter */}
        <div className="flex flex-wrap items-center gap-2" data-testid="dashboard-filter">
          <Filter size={14} className="text-slate-400" />
          {["day","week","month","custom"].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-semibold transition-colors",
                period === p
                  ? "bg-orange-600 text-white"
                  : "bg-white border border-slate-200 text-slate-600 hover:border-orange-300"
              )}
              data-testid={`filter-${p}`}
            >
              {p === "day" ? "Today" : p === "week" ? "Week" : p === "month" ? "Month" : "Custom"}
            </button>
          ))}
          {period === "custom" && (
            <div className="flex items-center gap-1.5 mt-1 sm:mt-0">
              <Input
                type="date"
                value={custom.start}
                max={todayIST()}
                onChange={(e) => {
                  const s = { ...custom, start: e.target.value };
                  setCustom(s);
                  if (s.start && s.end) fetchFiltered("custom", s);
                }}
                className="h-8 w-36 text-xs bg-white"
              />
              <span className="text-slate-400 text-xs">to</span>
              <Input
                type="date"
                value={custom.end}
                max={todayIST()}
                onChange={(e) => {
                  const s = { ...custom, end: e.target.value };
                  setCustom(s);
                  if (s.start && s.end) fetchFiltered("custom", s);
                }}
                className="h-8 w-36 text-xs bg-white"
              />
            </div>
          )}
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-4 gap-4">
        <KPI testid="kpi-today-sales"
             icon={CalendarDays}
             label={`${rangeLabel} Sales`}
             value={loading ? "..." : inr(kpiSales)}
             color="orange" />
        <KPI testid="kpi-today-expenses"
             icon={Wallet}
             label={`${rangeLabel} Expenses`}
             value={loading ? "..." : inr(kpiExp)}
             color="amber" />
        <KPI testid="kpi-today-pnl"
             icon={isLoss ? TrendingDown : TrendingUp}
             label={`${rangeLabel} P&L`}
             value={loading ? "..." : inr(Math.abs(kpiNet))}
             hint={loading ? null : periodPnlHint}
             color={isProfit ? "green" : isLoss ? "red" : "slate"} />
        <KPI testid="kpi-total-sales"
             icon={IndianRupee}
             label="Total Sales (All Time)"
             value={inr(data.total_sales)}
             color="green" />
        <KPI testid="kpi-total-spent"
             icon={ShoppingBag}
             label="Total Spent (All Time)"
             value={inr(data.total_spent)}
             color="amber" />
        <KPI testid="kpi-profit"
             icon={Scale}
             label="Overall P&L (All Time)"
             value={inr(Math.abs(data.profit))}
             hint={allTimePnlHint}
             color={data.profit > 0 ? "green" : data.profit < 0 ? "red" : "slate"} />
        <KPI testid="kpi-low-stock"
             icon={AlertTriangle}
             label="Low Stock Items"
             value={data.low_stock_count}
             color="amber" />
        <KPI testid="kpi-out-stock"
             icon={PackageX}
             label="Out of Stock"
             value={data.out_of_stock_count}
             color="red" />
      </div>

      {/* Charts row 1 — Sales trend + Stock health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="rounded-2xl border-orange-900/10 shadow-sm lg:col-span-2" data-testid="sales-trend-card">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">Daily Sales — Last 30 Days</h3>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.sales_trend} margin={{ left: 0, right: 16, bottom: 0, top: 4 }}>
                  <CartesianGrid stroke="#F0E1D3" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "#64748B" }}
                    tickFormatter={fmtXDate}
                    ticks={data.sales_trend
                      .map((d, i) => i % 3 === 0 ? d.date : null)
                      .filter(Boolean)}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#64748B" }}
                    tickFormatter={fmtTick}
                    tickCount={5}
                    allowDecimals={false}
                    width={52}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip formatter={(v) => inr(v)} labelFormatter={fmtDate} />
                  <Line
                    type="monotone"
                    dataKey="amount"
                    stroke="#E65C00"
                    strokeWidth={2.5}
                    dot={SmartDot}
                    activeDot={{ r: 4, fill: "#E65C00" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="stock-health-card">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">Stock Health</h3>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" innerRadius={48} outerRadius={72} paddingAngle={2}>
                    {pieData.map((e) => <Cell key={e.name} fill={e.color} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-xs mt-1">
              {pieData.map((p) => (
                <div key={p.name}>
                  <div className="font-display font-bold text-xl" style={{ color: p.color }}>{p.value}</div>
                  <div className="text-slate-500 leading-tight">{p.name}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts row 2 — Category spend + Expense breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="category-spend-card">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Purchase Spend by Category</h3>
            <div className="space-y-3">
              {data.category_spend.length === 0
                ? <p className="text-sm text-slate-500">No purchase data yet.</p>
                : data.category_spend.map((c) => (
                    <div key={c.category}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium text-slate-700 truncate mr-2">{c.category}</span>
                        <span className="tabular-nums text-slate-900 font-semibold shrink-0">{inr(c.amount)}</span>
                      </div>
                      <Progress value={(c.amount / maxCat) * 100} className="h-2" />
                    </div>
                  ))
              }
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="expense-spend-card">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Expense Breakdown</h3>
            <div className="space-y-3">
              {(!data.expense_category_spend || data.expense_category_spend.length === 0)
                ? <p className="text-sm text-slate-500">No expense data yet.</p>
                : (data.expense_category_spend || []).map((c) => (
                    <div key={c.category}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium text-slate-700 truncate mr-2">{c.category}</span>
                        <span className="tabular-nums text-slate-900 font-semibold shrink-0">{inr(c.amount)}</span>
                      </div>
                      <Progress value={(c.amount / maxExp) * 100} className="h-2" />
                    </div>
                  ))
              }
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top items */}
      <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="top-items-card">
        <CardContent className="p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Top 5 Items by Cost</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
            {data.top_items.length === 0
              ? <p className="text-sm text-slate-500">No purchase data yet.</p>
              : data.top_items.map((it, i) => (
                  <div key={it.name} className="flex items-center justify-between p-3 rounded-xl bg-orange-50/50">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="h-7 w-7 shrink-0 rounded-lg bg-orange-600 text-white flex items-center justify-center text-xs font-bold">{i + 1}</div>
                      <div className="font-medium text-slate-800 truncate text-sm">{it.name}</div>
                    </div>
                    <div className="tabular-nums font-semibold text-slate-900 ml-2 shrink-0 text-sm">{inr(it.amount)}</div>
                  </div>
                ))
            }
          </div>
        </CardContent>
      </Card>

    </div>
  );
}

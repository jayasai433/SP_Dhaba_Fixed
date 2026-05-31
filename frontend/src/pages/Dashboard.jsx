import { useEffect, useState } from "react";
import api from "@/lib/api";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  IndianRupee, TrendingUp, ShoppingBag, AlertTriangle, PackageX, CalendarDays
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip,
  PieChart, Pie, Cell, CartesianGrid
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";

const STATUS_COLORS = { in: "#2E7D32", low: "#F57F17", out: "#C62828" };

function KPI({ icon: Icon, label, value, hint, color = "orange", testid }) {
  const palette = {
    orange: "bg-orange-50 text-orange-600",
    green: "bg-green-50 text-green-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
    slate: "bg-slate-100 text-slate-700",
  }[color];
  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid={testid}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${palette}`}>
            <Icon size={20} />
          </div>
          {hint && <span className="text-[11px] uppercase tracking-wider text-slate-400">{hint}</span>}
        </div>
        <div className="mt-4">
          <div className="text-xs font-semibold tracking-widest uppercase text-slate-500">{label}</div>
          <div className="font-display font-bold text-3xl text-slate-900 mt-1 tabular-nums">{value}</div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/dashboard").then(({ data }) => setData(data));
    const t = setInterval(() => api.get("/dashboard").then(({ data }) => setData(data)), 60000);
    return () => clearInterval(t);
  }, []);

  if (!data) {
    return (
      <div className="space-y-6" data-testid="dashboard-loading">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  const maxCat = Math.max(1, ...data.category_spend.map((c) => c.amount));
  const pieData = [
    { name: "In Stock", value: data.stock_health.in, color: STATUS_COLORS.in },
    { name: "Low Stock", value: data.stock_health.low, color: STATUS_COLORS.low },
    { name: "Out of Stock", value: data.stock_health.out, color: STATUS_COLORS.out },
  ];

  return (
    <div className="space-y-6 animate-fade-up" data-testid="dashboard-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Overview</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">Dashboard</h1>
        <p className="text-slate-600 text-sm mt-1">{fmtDate(todayIST())} · All amounts in INR (₹)</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <KPI testid="kpi-today-sales" icon={CalendarDays} label="Today's Sales" value={inr(data.today_sales)} color="orange" />
        <KPI testid="kpi-total-sales" icon={IndianRupee} label="Total Sales" value={inr(data.total_sales)} color="green" />
        <KPI testid="kpi-total-spent" icon={ShoppingBag} label="Total Spent" value={inr(data.total_spent)} color="amber" />
        <KPI testid="kpi-profit" icon={TrendingUp} label="Est. Profit" value={inr(data.profit)} color={data.profit >= 0 ? "green" : "red"} />
        <KPI testid="kpi-low-stock" icon={AlertTriangle} label="Low Stock" value={data.low_stock_count} color="amber" />
        <KPI testid="kpi-out-stock" icon={PackageX} label="Out of Stock" value={data.out_of_stock_count} color="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="rounded-2xl border-orange-900/10 shadow-sm lg:col-span-2" data-testid="sales-trend-card">
          <CardContent className="p-5">
            <div className="flex items-baseline justify-between mb-3">
              <h3 className="font-display text-lg font-semibold text-slate-900">Daily Sales — Last 30 Days</h3>
            </div>
            <div className="h-64 w-full" style={{ minHeight: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.sales_trend}>
                  <CartesianGrid stroke="#F0E1D3" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} tickFormatter={(d) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 11, fill: "#64748B" }} tickFormatter={(v) => `₹${v}`} />
                  <Tooltip formatter={(v) => inr(v)} labelFormatter={fmtDate} />
                  <Line type="monotone" dataKey="amount" stroke="#E65C00" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="stock-health-card">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">Stock Health</h3>
            <div className="h-48" style={{ minHeight: 180 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" innerRadius={50} outerRadius={75} paddingAngle={2}>
                    {pieData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-xs mt-2">
              {pieData.map((p) => (
                <div key={p.name}>
                  <div className="font-display font-bold text-lg" style={{ color: p.color }}>{p.value}</div>
                  <div className="text-slate-500">{p.name}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="category-spend-card">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Category-wise Spend</h3>
            <div className="space-y-3">
              {data.category_spend.length === 0 && (
                <p className="text-sm text-slate-500">No purchase data yet.</p>
              )}
              {data.category_spend.map((c) => (
                <div key={c.category}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="font-medium text-slate-700">{c.category}</span>
                    <span className="tabular-nums text-slate-900 font-semibold">{inr(c.amount)}</span>
                  </div>
                  <Progress value={(c.amount / maxCat) * 100} className="h-2" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="top-items-card">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Top 5 Items by Cost</h3>
            <div className="space-y-3">
              {data.top_items.length === 0 && (
                <p className="text-sm text-slate-500">No purchase data yet.</p>
              )}
              {data.top_items.map((it, i) => (
                <div key={it.name} className="flex items-center justify-between p-3 rounded-xl bg-orange-50/50">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-orange-600 text-white flex items-center justify-center text-sm font-bold">{i + 1}</div>
                    <div className="font-medium text-slate-800">{it.name}</div>
                  </div>
                  <div className="tabular-nums font-semibold text-slate-900">{inr(it.amount)}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

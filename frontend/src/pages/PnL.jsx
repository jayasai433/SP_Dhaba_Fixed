import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { inr, fmtDate } from "@/lib/format";
import { Download, TrendingUp, TrendingDown } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, ReferenceLine
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function Row({ label, value, neg, big }) {
  const v = neg ? -Math.abs(value) : value;
  return (
    <div className={cn("flex justify-between py-3 px-4 border-b last:border-0", big && "bg-orange-50/60")}>
      <span className={cn("text-sm", big ? "font-display font-bold text-base text-slate-900" : "text-slate-600")}>{label}</span>
      <span className={cn("tabular-nums", big ? "font-display font-bold text-xl" : "font-semibold text-slate-900",
        big && (value >= 0 ? "text-green-700" : "text-red-700"))}>
        {neg ? "-" : ""}{inr(Math.abs(value))}
      </span>
    </div>
  );
}

export default function PnL() {
  const [period, setPeriod] = useState("today");
  const [pnl, setPnl] = useState(null);
  const [error, setError] = useState(false);
  const [trend, setTrend] = useState([]);

  useEffect(() => {
    api.get("/pnl", { params: { period } })
      .then(({ data }) => setPnl(data))
      .catch(() => setError(true));
  }, [period]);

  useEffect(() => {
    api.get("/pnl/trend", { params: { days: 30 } })
      .then(({ data }) => setTrend(data))
      .catch(() => setError(true));
  }, []);

  const download = async () => {
    try {
      const { data, headers } = await api.get("/pnl/export", { params: { period }, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      const cd = headers["content-disposition"] || "";
      const m = cd.match(/filename="?([^"]+)"?/);
      a.download = m ? m[1] : `pnl-${period}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to export PDF. Please try again.");
    }
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <TrendingDown size={40} className="text-orange-400 mb-3" />
        <p className="font-medium">Could not load P&L data</p>
        <p className="text-sm mt-1">Check your connection and refresh the page</p>
      </div>
    );
  }

  if (!pnl) {
    return <div className="space-y-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-96 rounded-2xl" /></div>;
  }

  const isProfit = pnl.net_profit >= 0;

  return (
    <div className="space-y-6 animate-fade-up" data-testid="pnl-page">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Financials</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Profit & Loss</h1>
          <p className="text-slate-600 text-sm mt-1">
            {pnl.start ? `${fmtDate(pnl.start)} → ${fmtDate(pnl.end)}` : "All time"}
          </p>
        </div>
        <Button onClick={download} data-testid="pnl-export-button" className="rounded-full bg-orange-600 hover:bg-orange-700">
          <Download size={16} className="mr-1" />Export PDF
        </Button>
      </div>

      <Tabs value={period} onValueChange={setPeriod}>
        <TabsList className="bg-orange-50 p-1 rounded-full">
          <TabsTrigger value="today" data-testid="pnl-tab-today" className="rounded-full">Today</TabsTrigger>
          <TabsTrigger value="week" data-testid="pnl-tab-week" className="rounded-full">This Week</TabsTrigger>
          <TabsTrigger value="month" data-testid="pnl-tab-month" className="rounded-full">This Month</TabsTrigger>
          <TabsTrigger value="all" data-testid="pnl-tab-all" className="rounded-full">All Time</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="rounded-2xl border-orange-900/10 shadow-sm lg:col-span-2" data-testid="pnl-statement-card">
          <CardContent className="p-0">
            <Row label="Revenue (Sales)" value={pnl.revenue} />
            <Row label="Cost of Goods (Purchases)" value={pnl.cogs} neg />
            <Row label="Operating Expenses" value={pnl.expenses} neg />
            <Row label="Salaries Paid" value={pnl.salaries} neg />
            <Row label={isProfit ? "Net Profit" : "Net Loss"} value={pnl.net_profit} big />
          </CardContent>
        </Card>

        <Card className={cn("rounded-2xl shadow-sm border-2",
            isProfit ? "bg-green-50/50 border-green-300" : "bg-red-50/50 border-red-300")}
          data-testid="pnl-summary-card">
          <CardContent className="p-6 text-center">
            <div className={cn("mx-auto h-14 w-14 rounded-2xl flex items-center justify-center",
              isProfit ? "bg-green-600 text-white" : "bg-red-600 text-white")}>
              {isProfit ? <TrendingUp size={28} /> : <TrendingDown size={28} />}
            </div>
            <div className={cn("font-display text-4xl font-bold mt-4 tabular-nums",
              isProfit ? "text-green-700" : "text-red-700")} data-testid="pnl-net-amount">
              {inr(Math.abs(pnl.net_profit))}
            </div>
            <div className={cn("text-sm font-semibold mt-1", isProfit ? "text-green-700" : "text-red-700")}>
              {isProfit ? "Net Profit" : "Net Loss"}
            </div>
            {pnl.revenue > 0 && (
              <div className="text-xs text-slate-500 mt-3">
                Margin: <span className="tabular-nums font-semibold">
                  {((pnl.net_profit / pnl.revenue) * 100).toFixed(1)}%
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="pnl-trend-card">
        <CardContent className="p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">Daily Net P&L — Last 30 Days</h3>
          <div className="h-64" style={{ minHeight: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <CartesianGrid stroke="#F0E1D3" strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 11, fill: "#64748B" }} tickFormatter={(v) => `₹${v}`} />
                <Tooltip formatter={(v) => inr(v)} labelFormatter={fmtDate} />
                <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="net" stroke="#E65C00" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

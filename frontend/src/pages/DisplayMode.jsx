import { useEffect, useState, useCallback } from "react";
import logger from "@/lib/logger";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useBusinessProfile } from "@/contexts/BusinessProfileContext";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LogOut, Maximize2, TrendingUp, ShoppingCart, Wallet, IndianRupee } from "lucide-react";

async function requestWakeLock() {
  try {
    if ("wakeLock" in navigator) await navigator.wakeLock.request("screen");
  } catch (e) { logger.log("Wake Lock not available:", e); }
}

const PERIODS = [
  { key: "today", label: "Today" },
  { key: "week",  label: "This Week" },
  { key: "month", label: "This Month" },
  { key: "custom", label: "Custom" },
];

function KpiCard({ icon: Icon, label, value, color, testid }) {
  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 p-4 text-center" data-testid={testid}>
      <div className={`flex items-center justify-center gap-1.5 text-xs uppercase tracking-widest mb-1 ${color}`}>
        <Icon size={12} />{label}
      </div>
      <div className={`font-display text-2xl font-bold tabular-nums ${color}`}>
        {inr(value)}
      </div>
    </div>
  );
}

export default function DisplayMode() {
  const { user }    = useAuth();
  const navigate    = useNavigate();
  const { profile } = useBusinessProfile();
  const [now, setNow]       = useState(new Date());
  const [period, setPeriod] = useState("today");
  const [custom, setCustom] = useState({ start: "", end: "" });
  const [data, setData]     = useState({ sales: 0, purchases: 0, expenses: 0 });
  const [error, setError]   = useState(false);

  const load = useCallback(async () => {
    try {
      let params = {};
      if (period === "today") {
        params = { start: todayIST(), end: todayIST() };
      } else if (period === "week") {
        const d = new Date(); d.setDate(d.getDate() - 6);
        params = { start: d.toISOString().slice(0, 10), end: todayIST() };
      } else if (period === "month") {
        params = { start: todayIST().slice(0, 7) + "-01", end: todayIST() };
      } else if (period === "custom" && custom.start && custom.end) {
        params = { start: custom.start, end: custom.end };
      } else {
        return; // custom not filled yet
      }

      const [salesData, purchasesData, expensesData] = await Promise.all([
        api.get("/sales",     { params }).then((r) => r.data),
        api.get("/purchases", { params }).then((r) => r.data),
        api.get("/expenses",  { params }).then((r) => r.data),
      ]);

      const sales     = salesData.reduce((a, b) => a + (b.total_amount || 0), 0);
      const purchases = purchasesData.reduce((a, b) => a + (b.total_cost || 0), 0);
      const expenses  = expensesData.reduce((a, b) => a + (b.amount || 0), 0);

      setData({ sales, purchases, expenses });
      setError(false);
    } catch (err) {
      logger.error("DisplayMode load failed:", err);
      setError(true);
    }
  }, [period, custom]);

  useEffect(() => {
    load();
    const t1 = setInterval(load, 60000);
    const t2 = setInterval(() => setNow(new Date()), 1000);
    return () => { clearInterval(t1); clearInterval(t2); };
  }, [load]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    requestWakeLock();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") requestWakeLock();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  const fullscreen = (e) => {
    e.preventDefault(); e.stopPropagation();
    if (document.fullscreenElement) {
      document.exitFullscreen().catch((err) => logger.error("exitFullscreen failed:", err));
    } else {
      document.documentElement.requestFullscreen().catch((err) => logger.error("requestFullscreen failed:", err));
    }
  };

  const exitDisplay = async (e) => {
    e.preventDefault(); e.stopPropagation();
    if (document.fullscreenElement) {
      try { await document.exitFullscreen(); } catch (err) { logger.error("exitFullscreen failed:", err); }
    }
    const role = user?.role;
    if (role === "staff") navigate("/stock");
    else navigate("/dashboard");
  };

  const profit = data.sales - data.purchases - data.expenses;

  return (
    <div className="-m-4 md:-m-8 -mt-6 md:-mt-8 min-h-screen bg-[#2D1606] text-white"
      data-testid="display-mode-page">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-orange-600 flex items-center justify-center font-display font-bold">SP</div>
          <div>
            <div className="font-display text-lg font-semibold">{profile.name}</div>
            <div className="text-xs text-orange-200/70 tabular-nums">
              {fmtDate(todayIST())} · {now.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" })}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={fullscreen} className="text-white hover:bg-white/10 rounded-full">
            <Maximize2 size={16} className="mr-2" />Fullscreen
          </Button>
          <Button variant="ghost" onClick={exitDisplay} className="text-white hover:bg-white/10 rounded-full">
            <LogOut size={16} className="mr-2" />Exit
          </Button>
        </div>
      </div>

      <div className="flex flex-col items-center p-6 gap-6 min-h-[80vh]">

        {/* Period selector */}
        <div className="flex gap-2 bg-white/5 rounded-2xl p-1">
          {PERIODS.map((p) => (
            <button key={p.key} onClick={() => setPeriod(p.key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                period === p.key
                  ? "bg-orange-600 text-white"
                  : "text-orange-200/60 hover:text-white"
              }`}>
              {p.label}
            </button>
          ))}
        </div>

        {/* Custom date pickers */}
        {period === "custom" && (
          <div className="flex gap-3 items-center">
            <Input type="date" value={custom.start}
              onChange={(e) => setCustom((p) => ({ ...p, start: e.target.value }))}
              className="h-10 bg-white/10 border-white/20 text-white w-40" />
            <span className="text-orange-200/50">to</span>
            <Input type="date" value={custom.end}
              onChange={(e) => setCustom((p) => ({ ...p, end: e.target.value }))}
              className="h-10 bg-white/10 border-white/20 text-white w-40" />
          </div>
        )}

        {/* Hero — Profit */}
        <div className="rounded-3xl bg-white/5 border border-white/10 p-10 text-center w-full max-w-lg">
          <div className="flex items-center justify-center gap-2 text-orange-200/70 text-sm uppercase tracking-widest mb-2">
            <IndianRupee size={14} /> Net Profit
          </div>
          <div className={`font-display text-7xl font-bold tabular-nums ${profit >= 0 ? "text-green-400" : "text-red-400"}`}
            data-testid="display-profit">
            {inr(profit)}
          </div>
          <div className="text-orange-200/40 text-xs mt-2">Sales − Purchases − Expenses</div>
        </div>

        {/* KPI grid */}
        <div className="grid grid-cols-3 gap-3 w-full max-w-lg">
          <KpiCard icon={TrendingUp} label="Sales"     value={data.sales}     color="text-orange-300" testid="display-sales" />
          <KpiCard icon={ShoppingCart} label="Purchases" value={data.purchases} color="text-blue-300"   testid="display-purchases" />
          <KpiCard icon={Wallet}      label="Expenses"  value={data.expenses}  color="text-purple-300" testid="display-expenses" />
        </div>

        {/* Footer */}
        <div className="text-orange-200/30 text-xs text-center mt-2">
          SP Royal Punjabi Family Dhaba · Auto-refreshes every 60s
        </div>
      </div>
    </div>
  );
}

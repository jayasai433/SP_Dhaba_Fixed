import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useBusinessProfile } from "@/contexts/BusinessProfileContext";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { LogOut, Maximize2 } from "lucide-react";

const STATUS_BG = {
  in: "bg-[#1B5E20]/40 border-[#2E7D32]/60",
  low: "bg-[#F57F17]/30 border-[#F57F17]/60",
  out: "bg-[#C62828]/40 border-[#C62828]/60",
};

// Wake Lock — prevents screen from dimming in Display Mode
async function requestWakeLock() {
  try {
    if ("wakeLock" in navigator) {
      await navigator.wakeLock.request("screen");
    }
  } catch (e) {
    console.log("Wake Lock not available:", e);
  }
}

export default function DisplayMode() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { profile } = useBusinessProfile();
  const [stock, setStock] = useState([]);
  const [today, setToday] = useState(0);
  const [alerts, setAlerts] = useState([]);
  const [now, setNow] = useState(new Date());
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, d, a] = await Promise.all([
        api.get("/stock").then((r) => r.data),
        api.get("/sales/check/" + todayIST()).then((r) => r.data),
        api.get("/alerts").then((r) => r.data),
      ]);
      setStock(s.filter((x) => x.is_active));
      setToday(d.entry?.total_amount || 0);
      setAlerts(a);
      setError(false);
    } catch (err) {
      console.error(err);
      setError(true);
    }
  }, []);

  useEffect(() => {
    load();
    const t1 = setInterval(load, 60000);
    const t2 = setInterval(() => setNow(new Date()), 1000);
    return () => { clearInterval(t1); clearInterval(t2); };
  }, [load]);

  // Prevent screen from dimming in Display Mode
  useEffect(() => {
    requestWakeLock();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") requestWakeLock();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  const fullscreen = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (document.fullscreenElement) {
      document.exitFullscreen().catch((err) => console.error(err));
    } else {
      document.documentElement.requestFullscreen().catch((err) => console.error(err));
    }
  };

  const exitDisplay = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Exit fullscreen first if active, then navigate to home
    if (document.fullscreenElement) {
      try { await document.exitFullscreen(); } catch (err) { console.error(err); }
    }
    // Navigate based on role - never logout
    const role = user?.role;
    if (role === "staff") navigate("/stock");
    else if (role === "admin") navigate("/dashboard");
    else navigate("/dashboard");
  };

  const counts = stock.reduce((acc, s) => { acc[s.status] = (acc[s.status] || 0) + 1; return acc; }, { in: 0, low: 0, out: 0 });
  const topAlerts = alerts.slice(0, 10);

  return (
    <div className="-m-4 md:-m-8 -mt-6 md:-mt-8 min-h-screen bg-[#2D1606] text-white" data-testid="display-mode-page">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-orange-600 flex items-center justify-center font-display font-bold">SP</div>
          <div>
            <div className="font-display text-lg font-semibold">{profile.name}</div>
            <div className="text-xs text-orange-200/70 tabular-nums">{fmtDate(todayIST())} · {now.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" })}</div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={fullscreen} data-testid="display-fullscreen" className="text-white hover:bg-white/10 rounded-full"><Maximize2 size={16} className="mr-2" />Fullscreen</Button>
          <Button variant="ghost" onClick={exitDisplay} data-testid="display-exit" className="text-white hover:bg-white/10 rounded-full"><LogOut size={16} className="mr-2" />Exit</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6">
        <div className="lg:col-span-4 space-y-4">
          <div className="rounded-2xl bg-white/5 border border-white/10 p-6">
            <div className="text-orange-200/70 text-xs uppercase tracking-widest">Today's Sales</div>
            <div className="font-display text-6xl font-bold tabular-nums mt-2 text-orange-300">{inr(today)}</div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-2xl bg-green-900/40 border border-green-500/30 p-4 text-center">
              <div className="text-xs text-green-200">In Stock</div>
              <div className="font-display font-bold text-3xl tabular-nums">{counts.in}</div>
            </div>
            <div className="rounded-2xl bg-amber-900/40 border border-amber-500/30 p-4 text-center">
              <div className="text-xs text-amber-200">Low</div>
              <div className="font-display font-bold text-3xl tabular-nums">{counts.low}</div>
            </div>
            <div className="rounded-2xl bg-red-900/40 border border-red-500/30 p-4 text-center">
              <div className="text-xs text-red-200">Out</div>
              <div className="font-display font-bold text-3xl tabular-nums">{counts.out}</div>
            </div>
          </div>

          <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
            <div className="font-display font-semibold mb-3">Top Alerts ({alerts.length})</div>
            {topAlerts.length === 0 ? (
              <div className="text-sm text-green-300">✓ All items in stock — well done!</div>
            ) : (
              <div className="space-y-2">
                {topAlerts.map((a) => (
                  <div key={a.item_id} data-testid={`display-alert-${a.item_id}`} className={`flex items-center justify-between px-3 py-2 rounded-xl border ${STATUS_BG[a.status]}`}>
                    <div>
                      <div className="font-medium">{a.name}</div>
                      <div className="text-xs text-white/60">{a.category}</div>
                    </div>
                    <div className="tabular-nums font-display font-bold text-lg">{a.qty_left} {a.unit}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-8">
          <div className="font-display font-semibold mb-3 text-orange-200">Live Stock</div>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3" data-testid="display-stock-grid">
            {stock.map((s) => (
              <div key={s.item_id}
                className={`p-4 rounded-2xl border ${STATUS_BG[s.status]}`}>
                <div className="text-[10px] uppercase tracking-widest opacity-70">{s.category}</div>
                <div className="font-display font-semibold truncate">{s.name}</div>
                <div className="font-display font-bold text-3xl tabular-nums mt-2">{s.qty_left} <span className="text-base font-normal opacity-70">{s.unit}</span></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

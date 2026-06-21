import { useEffect, useState, useCallback } from "react";
import logger from "@/lib/logger";
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
    logger.log("Wake Lock not available:", e);
  }
}

export default function DisplayMode() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { profile } = useBusinessProfile();
  const [today, setToday] = useState(0);
  const [week, setWeek] = useState(0);
  const [month, setMonth] = useState(0);
  const [now, setNow] = useState(new Date());
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    try {
      const [todayData, weekData, monthData] = await Promise.all([
        api.get("/sales/check/" + todayIST()).then((r) => r.data),
        api.get("/sales", { params: { period: "week" } }).then((r) => r.data),
        api.get("/sales", { params: { period: "month" } }).then((r) => r.data),
      ]);
      setToday(todayData.entry?.total_amount || 0);
      setWeek(weekData.reduce((a, b) => a + (b.total_amount || 0), 0));
      setMonth(monthData.reduce((a, b) => a + (b.total_amount || 0), 0));
      setError(false);
    } catch (err) {
      logger.error("DisplayMode load failed:", err);
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
  // requestWakeLock is a module-level stable function — empty deps is intentional
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
    e.preventDefault();
    e.stopPropagation();
    if (document.fullscreenElement) {
      document.exitFullscreen().catch((err) => logger.error("exitFullscreen failed:", err));
    } else {
      document.documentElement.requestFullscreen().catch((err) => logger.error("requestFullscreen failed:", err));
    }
  };

  const exitDisplay = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Exit fullscreen first if active, then navigate to home
    if (document.fullscreenElement) {
      try { await document.exitFullscreen(); } catch (err) { logger.error("exitFullscreen failed:", err); }
    }
    // Navigate based on role - never logout
    const role = user?.role;
    if (role === "staff") navigate("/stock");
    else if (role === "admin") navigate("/dashboard");
    else navigate("/dashboard");
  };


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

      {/* Clean sales-only display — stock grid removed (not live, re-enable in v2.0) */}
      <div className="flex flex-col items-center justify-center flex-1 p-6 gap-6 min-h-[80vh]">

        {/* Today's Sales — hero */}
        <div className="rounded-3xl bg-white/5 border border-white/10 p-10 text-center w-full max-w-lg">
          <div className="text-orange-200/70 text-sm uppercase tracking-widest mb-2">Today's Sales</div>
          <div className="font-display text-7xl font-bold tabular-nums text-orange-300" data-testid="display-today-sales">
            {inr(today)}
          </div>
        </div>

        {/* Weekly + Monthly */}
        <div className="grid grid-cols-2 gap-4 w-full max-w-lg">
          <div className="rounded-2xl bg-white/5 border border-white/10 p-6 text-center">
            <div className="text-orange-200/70 text-xs uppercase tracking-widest mb-1">This Week</div>
            <div className="font-display text-3xl font-bold tabular-nums text-white" data-testid="display-week-sales">
              {inr(week)}
            </div>
          </div>
          <div className="rounded-2xl bg-white/5 border border-white/10 p-6 text-center">
            <div className="text-orange-200/70 text-xs uppercase tracking-widest mb-1">This Month</div>
            <div className="font-display text-3xl font-bold tabular-nums text-white" data-testid="display-month-sales">
              {inr(month)}
            </div>
          </div>
        </div>

        {/* Motivational footer */}
        <div className="text-orange-200/40 text-sm text-center mt-4">
          SP Royal Punjabi Family Dhaba · {fmtDate(todayIST())}
        </div>
      </div>
    </div>
  );
}

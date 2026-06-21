import { useState, useEffect, useCallback } from "react";
import logger from "@/lib/logger";
import { Link, useLocation, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useBusinessProfile } from "@/contexts/BusinessProfileContext";
import { WifiOff } from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, Package, ShoppingCart, ClipboardCheck, IndianRupee,
  Boxes, BellRing, Settings, LogOut, Tv, Menu, X,
  Wallet, Users, LineChart, Trash2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import StagingBanner from "@/components/StagingBanner";
import { Badge } from "@/components/ui/badge";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "viewer", "staff"] },
  { to: "/stock", label: "Live Stock", icon: Boxes, roles: ["admin", "staff", "viewer"] },
  { to: "/alerts", label: "Alerts", icon: BellRing, roles: ["admin", "staff", "viewer"], badge: true },
  { to: "/purchases", label: "Purchases", icon: ShoppingCart, roles: ["admin", "staff"] },
  { to: "/closing-stock", label: "Closing Stock", icon: ClipboardCheck, roles: ["admin", "staff"] },
  { to: "/sales", label: "Sales", icon: IndianRupee, roles: ["admin", "staff"] },
  { to: "/expenses", label: "Expenses", icon: Wallet, roles: ["admin", "staff"] },
  { to: "/wastage", label: "Wastage", icon: Trash2, roles: ["admin", "staff", "viewer"] },
  { to: "/salaries", label: "Salaries", icon: Users, roles: ["admin"] },
  { to: "/pnl", label: "P&L Statement", icon: LineChart, roles: ["admin", "viewer"] },
  { to: "/items", label: "Item Master", icon: Package, roles: ["admin"] },
  { to: "/display", label: "Display Mode", icon: Tv, roles: ["viewer", "admin", "staff"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["admin"] },
];

const MOBILE_NAV_BY_ROLE = {
  admin: ["/dashboard", "/stock", "/purchases", "/sales", "/closing-stock"],
  staff: ["/dashboard", "/stock", "/purchases", "/closing-stock", "/sales", "/expenses", "/display"],
  viewer: ["/dashboard", "/stock", "/alerts", "/pnl", "/display"],
};

export default function Layout() {
  const { user, logout } = useAuth();
  const { profile } = useBusinessProfile();
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  useEffect(() => {
    const goOffline = () => setIsOffline(true);
    const goOnline  = () => setIsOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online",  goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online",  goOnline);
    };
  }, []);
  const loc = useLocation();
  const [alertsCount, setAlertsCount] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetchAlerts = useCallback(() => {
    api.get("/alerts")
      .then(({ data }) => setAlertsCount(data.length))
      .catch((err) => logger.error("Alerts badge fetch failed:", err));
  }, []);

  useEffect(() => {
    fetchAlerts();
    const t = setInterval(fetchAlerts, 60000);
    return () => clearInterval(t);
  }, [fetchAlerts]);

  useEffect(() => { setDrawerOpen(false); }, [loc.pathname]);

  const visibleNav = NAV.filter((n) => n.roles.includes(user.role));
  const mobileNavRoutes = MOBILE_NAV_BY_ROLE[user.role] || [];
  const mobileNav = visibleNav.filter((n) => mobileNavRoutes.includes(n.to)).slice(0, 5);

  const SidebarContent = (
    <>
      <div className="flex items-center gap-3 px-2 mb-6">
        <div className="h-10 w-10 rounded-xl bg-orange-600 flex items-center justify-center text-white font-bold font-display shadow-lg shadow-orange-900/40">
          {profile.logo_base64 ? (
            <img src={profile.logo_base64} alt="logo" className="h-10 w-10 rounded-xl object-cover" />
          ) : "SP"}
        </div>
        <div className="leading-tight">
          <div className="font-display font-semibold text-white text-sm" data-testid="business-name">{profile.name}</div>
          <div className="text-[11px] text-orange-200/60">Operations Manager</div>
        </div>
      </div>
      <nav className="flex-1 flex flex-col gap-1">
        {visibleNav.map((n) => {
          const active = loc.pathname.startsWith(n.to);
          const Icon = n.icon;
          return (
            <Link
              key={n.to}
              to={n.to}
              data-testid={`sidebar-link-${n.to.slice(1)}`}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all",
                active
                  ? "bg-orange-600 text-white shadow-md shadow-orange-900/30"
                  : "text-orange-100/80 hover:bg-white/5"
              )}
            >
              <Icon size={18} />
              <span className="flex-1">{n.label}</span>
              {n.badge && alertsCount > 0 && (
                <Badge data-testid="sidebar-alerts-badge" className="bg-red-600 hover:bg-red-600 text-white">{alertsCount}</Badge>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="mt-4 pt-4 border-t border-white/10">
        <div className="px-3 py-2 text-xs text-orange-200/70">
          <div className="font-medium text-white" data-testid="current-user-name">{user.name}</div>
          <div className="uppercase tracking-wider text-[10px] mt-0.5">{user.role}</div>
        </div>
        <Button
          variant="ghost"
          onClick={logout}
          data-testid="logout-button"
          className="w-full justify-start text-orange-100 hover:bg-white/10 hover:text-white rounded-xl"
        >
          <LogOut size={16} className="mr-2" />Logout
        </Button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen flex bg-[#FFF8F0]" data-testid="app-shell">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-64 h-screen sticky top-0 bg-[#2D1606] p-4 z-40">
        {SidebarContent}
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/50" onClick={() => setDrawerOpen(false)} />
          <aside className="relative w-72 bg-[#2D1606] p-4 flex flex-col animate-fade-up">
            <button onClick={() => setDrawerOpen(false)} className="absolute top-3 right-3 text-white p-2" data-testid="close-drawer">
              <X size={20} />
            </button>
            {SidebarContent}
          </aside>
        </div>
      )}

      {/* Main */}
      <main className="flex-1 min-w-0 flex flex-col">
        {/* Mobile top bar */}
        <header className="md:hidden sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-orange-900/10 px-4 h-14 flex items-center justify-between">
          <button onClick={() => setDrawerOpen(true)} data-testid="open-drawer" className="p-2 -ml-2 text-slate-700">
            <Menu size={22} />
          </button>
          <div className="font-display font-semibold text-slate-900 text-sm truncate">{profile.name}</div>
          <div className="w-8 h-8 rounded-full bg-orange-100 text-orange-700 text-xs font-semibold flex items-center justify-center">
            {user.name?.[0]?.toUpperCase()}
          </div>
        </header>

        <StagingBanner />
        <div className="flex-1 px-4 py-6 pb-24 md:p-8 max-w-[1400px] w-full mx-auto">
          <Outlet />
        </div>

        {/* Mobile bottom nav */}
        <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-xl border-t border-orange-900/10 h-16 flex items-center justify-around px-2">
          {mobileNav.map((n) => {
            const active = loc.pathname.startsWith(n.to);
            const Icon = n.icon;
            return (
              <Link
                key={n.to}
                to={n.to}
                data-testid={`bottom-nav-${n.to.slice(1)}`}
                className={cn(
                  "relative flex flex-col items-center justify-center min-w-[56px] py-1 rounded-xl transition-all",
                  active ? "text-orange-600" : "text-slate-500"
                )}
              >
                <Icon size={20} />
                <span className="text-[10px] mt-0.5 font-medium">{n.label}</span>
                {n.badge && alertsCount > 0 && (
                  <span className="absolute top-0 right-2 h-4 min-w-[16px] px-1 text-[10px] rounded-full bg-red-600 text-white flex items-center justify-center">
                    {alertsCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </main>
    </div>
  );
}

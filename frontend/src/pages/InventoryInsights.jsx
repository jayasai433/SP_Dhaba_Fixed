/**
 * InventoryInsights — Inventory intelligence dashboard.
 *
 * Shows:
 *   1. Summary cards (total alerts, critical, recommendations)
 *   2. Anomaly alerts (spike, idle, low stock)
 *   3. Purchase recommendations ("Order X kg tomorrow")
 *   4. Today's ingredient cost breakdown
 *   5. 30-day cost trend chart
 *
 * Design:
 *   - No business logic — all in useInventoryInsights hook
 *   - Sub-components handle their own rendering
 *   - Clean, scannable on mobile
 */

import { useEffect } from "react";
import { useInventoryInsights } from "@/hooks/useInventoryInsights";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertTriangle, ShoppingCart, TrendingDown, TrendingUp,
  Minus, Package, IndianRupee, CheckCircle2, Clock
} from "lucide-react";
import { inr } from "@/lib/format";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";

// ── Severity config ────────────────────────────────────────────────────────
const SEVERITY = {
  critical: { bg: "bg-red-50",    border: "border-red-200",    text: "text-red-700",    badge: "bg-red-100 text-red-700",    icon: AlertTriangle },
  warning:  { bg: "bg-amber-50",  border: "border-amber-200",  text: "text-amber-700",  badge: "bg-amber-100 text-amber-700", icon: AlertTriangle },
  info:     { bg: "bg-blue-50",   border: "border-blue-200",   text: "text-blue-700",   badge: "bg-blue-100 text-blue-700",  icon: AlertTriangle },
};

const URGENCY = {
  high:   { badge: "bg-red-100 text-red-700",    label: "Order Today"    },
  medium: { badge: "bg-amber-100 text-amber-700", label: "Order Soon"    },
  low:    { badge: "bg-slate-100 text-slate-600", label: "When Possible" },
};

// ── Sub-components ─────────────────────────────────────────────────────────

function SummaryCards({ summary, totalCost }) {
  const cards = [
    {
      label: "Critical Alerts",
      value: summary.critical_alerts,
      icon: AlertTriangle,
      color: summary.critical_alerts > 0 ? "text-red-600" : "text-slate-400",
      bg: summary.critical_alerts > 0 ? "bg-red-50" : "bg-slate-50",
    },
    {
      label: "Total Alerts",
      value: summary.total_alerts,
      icon: AlertTriangle,
      color: "text-amber-600",
      bg: "bg-amber-50",
    },
    {
      label: "Order Today",
      value: summary.high_urgency_orders,
      icon: ShoppingCart,
      color: summary.high_urgency_orders > 0 ? "text-orange-600" : "text-slate-400",
      bg: summary.high_urgency_orders > 0 ? "bg-orange-50" : "bg-slate-50",
    },
    {
      label: "Ingredient Cost Today",
      value: inr(totalCost),
      icon: IndianRupee,
      color: "text-slate-700",
      bg: "bg-slate-50",
      isText: true,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <div key={c.label} className={`${c.bg} rounded-2xl p-4`}>
            <div className={`${c.color} mb-1`}><Icon size={18} /></div>
            <div className={`text-2xl font-bold ${c.color} tabular-nums`}>
              {c.value}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">{c.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function AlertCard({ alert }) {
  const sev = SEVERITY[alert.severity] || SEVERITY.info;
  const Icon = sev.icon;
  return (
    <div className={`${sev.bg} ${sev.border} border rounded-xl p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 flex-1">
          <Icon size={16} className={`${sev.text} mt-0.5 flex-shrink-0`} />
          <div className="flex-1">
            <p className={`font-semibold text-sm ${sev.text}`}>{alert.title}</p>
            <p className="text-slate-600 text-sm mt-0.5">{alert.message}</p>
            <p className="text-slate-500 text-xs mt-1.5">
              <span className="font-medium">Action: </span>{alert.action}
            </p>
          </div>
        </div>
        <Badge className={`${sev.badge} border-0 text-xs flex-shrink-0`}>
          {alert.severity}
        </Badge>
      </div>
    </div>
  );
}

function RecommendationCard({ rec }) {
  const urg = URGENCY[rec.urgency] || URGENCY.low;
  return (
    <div className="flex items-center justify-between p-4 rounded-xl bg-white border border-slate-100 hover:border-orange-200 transition-colors">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-full bg-orange-50 flex items-center justify-center flex-shrink-0">
          <ShoppingCart size={16} className="text-orange-600" />
        </div>
        <div>
          <p className="font-semibold text-slate-800 text-sm">{rec.item_name}</p>
          <p className="text-slate-500 text-xs mt-0.5">{rec.reason}</p>
        </div>
      </div>
      <div className="text-right flex-shrink-0 ml-4">
        <p className="font-bold text-slate-800 tabular-nums">
          {rec.recommended_qty} {rec.unit}
        </p>
        <p className="text-xs text-slate-400 tabular-nums">{inr(rec.estimated_cost)}</p>
        <Badge className={`${urg.badge} border-0 text-xs mt-1`}>{urg.label}</Badge>
      </div>
    </div>
  );
}

function CostBreakdown({ items, potentialSavings }) {
  if (!items || items.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400 text-sm">
        No closing stock recorded today yet
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {potentialSavings > 0 && (
        <div className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-xl px-4 py-2.5 text-sm mb-3">
          <span className="text-amber-700">Potential savings if zero wastage</span>
          <span className="text-amber-700 font-bold tabular-nums">{inr(potentialSavings)}</span>
        </div>
      )}
      {items.map((item) => (
        <div key={item.item_id}
          className="flex items-center justify-between px-4 py-2.5 rounded-xl bg-slate-50/60 hover:bg-slate-50">
          <div>
            <span className="font-medium text-slate-700 text-sm">{item.item_name}</span>
            <span className="text-slate-400 text-xs ml-2">
              {item.consumed} {item.unit} × {inr(item.price_per_unit)}
            </span>
          </div>
          <span className="font-semibold text-slate-800 tabular-nums text-sm">
            {inr(item.total_cost)}
          </span>
        </div>
      ))}
    </div>
  );
}

function TrendChart({ data }) {
  if (!data || data.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={160}>
      <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f97316" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${v}`} width={50} />
        <Tooltip
          formatter={(v, n) => [inr(v), n === "total_cost" ? "Ingredient Cost" : "Potential Savings"]}
          labelFormatter={(l) => `Date: ${l}`}
        />
        <Area type="monotone" dataKey="total_cost" stroke="#f97316"
          strokeWidth={2} fill="url(#costGrad)" name="total_cost" />
        <Area type="monotone" dataKey="potential_savings" stroke="#ef4444"
          strokeWidth={1.5} fill="none" strokeDasharray="4 2" name="potential_savings" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function InventoryInsights() {
  const { loading, error, insights, costTrend, loadInsights, loadCostTrend } =
    useInventoryInsights();

  useEffect(() => {
    loadInsights();
    loadCostTrend(30);
  }, [loadInsights, loadCostTrend]);

  if (loading) {
    return (
      <div className="space-y-4 animate-fade-up">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1,2,3,4].map(k => <Skeleton key={k} className="h-24 rounded-2xl" />)}
        </div>
        <Skeleton className="h-48 rounded-2xl" />
        <Skeleton className="h-48 rounded-2xl" />
      </div>
    );
  }

  if (error || !insights) {
    return (
      <div className="text-center py-16 text-slate-400">
        <Package size={40} className="mx-auto mb-3 opacity-40" />
        <p className="font-medium">No insights available yet</p>
        <p className="text-sm mt-1">
          Record closing stock for a few days to see intelligence insights
        </p>
      </div>
    );
  }

  const { alerts, recommendations, today_cost, summary } = insights;

  return (
    <div className="space-y-6 animate-fade-up" data-testid="inventory-insights-page">

      {/* Header */}
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-900">
          Inventory Intelligence
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Automated insights from your closing stock data
        </p>
      </div>

      {/* Summary Cards */}
      <SummaryCards summary={summary} totalCost={today_cost.total_cost} />

      {/* Alerts */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <AlertTriangle size={16} className="text-orange-500" />
            Alerts
            {summary.total_alerts > 0 && (
              <Badge className="bg-red-100 text-red-700 border-0 ml-1">
                {summary.total_alerts}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {alerts.length === 0 ? (
            <div className="flex items-center gap-2 text-green-700 bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm">
              <CheckCircle2 size={16} />
              All items within normal consumption range
            </div>
          ) : (
            alerts.map((a) => <AlertCard key={a.title} alert={a} />)
          )}
        </CardContent>
      </Card>

      {/* Purchase Recommendations */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <ShoppingCart size={16} className="text-orange-500" />
            Purchase Recommendations — Tomorrow
            {summary.high_urgency_orders > 0 && (
              <Badge className="bg-orange-100 text-orange-700 border-0 ml-1">
                {summary.high_urgency_orders} urgent
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {recommendations.length === 0 ? (
            <div className="flex items-center gap-2 text-green-700 bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm">
              <CheckCircle2 size={16} />
              All items have sufficient stock — no orders needed tomorrow
            </div>
          ) : (
            recommendations.map((r) => (
              <RecommendationCard key={r.item_id} rec={r} />
            ))
          )}
        </CardContent>
      </Card>

      {/* Today's Ingredient Cost */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <IndianRupee size={16} className="text-orange-500" />
            Today's Ingredient Cost
            <span className="ml-auto font-bold text-slate-800 tabular-nums">
              {inr(today_cost.total_cost)}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <CostBreakdown
            items={today_cost.items}
            potentialSavings={today_cost.potential_savings}
          />
        </CardContent>
      </Card>

      {/* Cost Trend */}
      {costTrend.length > 0 && (
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <TrendingDown size={16} className="text-orange-500" />
              30-Day Cost Trend
              <span className="text-xs text-slate-400 font-normal ml-1">
                (dashed = potential savings)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TrendChart data={costTrend} />
          </CardContent>
        </Card>
      )}

    </div>
  );
}

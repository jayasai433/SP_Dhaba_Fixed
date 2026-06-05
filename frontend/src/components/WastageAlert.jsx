/**
 * WastageAlert — displays high-variance items with visual severity.
 *
 * Reusable component:
 *   - Used in ClosingStock page
 *   - Can be used in Dashboard, P&L in future
 *   - No API calls — receives data via props (pure presentational)
 */

import { AlertTriangle, TrendingDown, CheckCircle2 } from "lucide-react";
import { inr } from "@/lib/format";

const SEVERITY = {
  critical: { color: "red",    icon: AlertTriangle,  label: "Critical Wastage" },
  high:     { color: "orange", icon: TrendingDown,   label: "High Variance"    },
  ok:       { color: "green",  icon: CheckCircle2,   label: "Within Limit"     },
};

function getSeverity(variancePct) {
  if (variancePct > 25) return SEVERITY.critical;
  if (variancePct > 10) return SEVERITY.high;
  return SEVERITY.ok;
}

export function WastageAlert({ items, wastage_cost_est }) {
  if (!items || items.length === 0) {
    return (
      <div className="flex items-center gap-2 text-green-700 bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm">
        <CheckCircle2 size={16} />
        <span>All items within acceptable variance — no significant wastage detected</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {wastage_cost_est > 0 && (
        <div className="flex items-center justify-between bg-red-50 border border-red-200 rounded-xl px-4 py-2.5 text-sm">
          <span className="text-red-700 font-medium">Estimated wastage cost today</span>
          <span className="text-red-700 font-bold tabular-nums">{inr(wastage_cost_est)}</span>
        </div>
      )}
      {items.map((item, i) => {
        const sev = getSeverity(item.variance_pct);
        const Icon = sev.icon;
        return (
          <div key={i}
            className={`flex items-center justify-between rounded-xl px-4 py-2.5 text-sm
              bg-${sev.color}-50 border border-${sev.color}-200`}>
            <div className="flex items-center gap-2">
              <Icon size={15} className={`text-${sev.color}-600`} />
              <span className={`font-medium text-${sev.color}-800`}>{item.item}</span>
            </div>
            <div className="text-right">
              <span className={`text-${sev.color}-700 font-semibold`}>
                {item.variance_pct}% variance
              </span>
              <span className="text-slate-500 ml-2 text-xs">
                ({item.variance > 0 ? "+" : ""}{item.variance} {item.unit} unaccounted)
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

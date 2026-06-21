/**
 * ConsumptionBadge — inline badge shown on LiveStock rows.
 * Shows daily rate, estimated days remaining, and reorder status.
 * Hides cleanly if no data (insufficient purchase history).
 */
import { Flame, Clock, CheckCircle2, AlertTriangle, AlertOctagon, HelpCircle } from "lucide-react";

const STATUS_CONFIG = {
  overdue: {
    icon: AlertOctagon,
    color: "text-red-700",
    bg: "bg-red-50 border-red-200",
    label: "Reorder now",
  },
  urgent: {
    icon: Flame,
    color: "text-orange-700",
    bg: "bg-orange-50 border-orange-200",
    label: "Reorder today",
  },
  soon: {
    icon: Clock,
    color: "text-amber-700",
    bg: "bg-amber-50 border-amber-200",
    label: "Reorder soon",
  },
  ok: {
    icon: CheckCircle2,
    color: "text-green-700",
    bg: "bg-green-50 border-green-200",
    label: "In stock",
  },
  unknown: {
    icon: HelpCircle,
    color: "text-slate-400",
    bg: "bg-slate-50 border-slate-200",
    label: "Unknown",
  },
};

const CONFIDENCE_LABEL = {
  high:   "High confidence",
  medium: "Medium confidence",
  low:    "Low confidence (few data points)",
};

export default function ConsumptionBadge({ rate }) {
  if (!rate || rate.status === "insufficient_data" || !rate.daily_rate) {
    return (
      <span className="text-xs text-slate-400 italic">
        Insufficient purchase history
      </span>
    );
  }

  const cfg  = STATUS_CONFIG[rate.status] || STATUS_CONFIG.unknown;
  const Icon = cfg.icon;

  return (
    <div
      className={`inline-flex flex-col gap-0.5 px-3 py-1.5 rounded-xl border text-xs ${cfg.bg}`}
      title={CONFIDENCE_LABEL[rate.confidence] || ""}
    >
      {/* Status + days remaining */}
      <div className={`flex items-center gap-1.5 font-semibold ${cfg.color}`}>
        <Icon size={12} />
        <span>
          {rate.est_days_remaining !== null
            ? rate.est_days_remaining <= 0
              ? "Overdue — reorder now"
              : `~${rate.est_days_remaining}d remaining`
            : cfg.label}
        </span>
      </div>

      {/* Daily rate */}
      <div className="text-slate-500">
        {rate.daily_rate} {rate.unit}/day avg
        {rate.reorder_by && rate.status !== "ok" && (
          <span className="ml-1">· reorder by {new Date(rate.reorder_by).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
        )}
      </div>

      {/* Low confidence warning */}
      {rate.confidence === "low" && (
        <div className="text-slate-400 text-[10px]">
          Based on {rate.data_points} purchases only
        </div>
      )}
    </div>
  );
}

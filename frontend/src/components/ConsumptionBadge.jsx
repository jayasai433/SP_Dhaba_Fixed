/**
 * ConsumptionBadge — shows estimated stock remaining based on purchase history.
 * Uses previous purchase qty / gap days = daily consumption rate.
 * Current batch qty - (days since purchase × rate) = estimated remaining.
 */
import { Flame, Clock, CheckCircle2, AlertOctagon, HelpCircle } from "lucide-react";

const STATUS_CONFIG = {
  overdue: {
    icon: AlertOctagon,
    color: "text-red-700",
    bg: "bg-red-50 border-red-200",
  },
  urgent: {
    icon: Flame,
    color: "text-orange-700",
    bg: "bg-orange-50 border-orange-200",
  },
  soon: {
    icon: Clock,
    color: "text-amber-700",
    bg: "bg-amber-50 border-amber-200",
  },
  ok: {
    icon: CheckCircle2,
    color: "text-green-700",
    bg: "bg-green-50 border-green-200",
  },
  unknown: {
    icon: HelpCircle,
    color: "text-slate-400",
    bg: "bg-slate-50 border-slate-200",
  },
};

export default function ConsumptionBadge({ rate }) {
  // Not enough data yet
  if (!rate || rate.status === "insufficient_data" || !rate.daily_rate) {
    return (
      <span className="text-xs text-slate-400 italic">
        Need 2+ purchases to estimate stock
      </span>
    );
  }

  const cfg  = STATUS_CONFIG[rate.status] || STATUS_CONFIG.unknown;
  const Icon = cfg.icon;

  const estRemaining = rate.est_remaining ?? 0;
  const daysLeft     = rate.est_days_remaining;
  const unit         = rate.unit;

  return (
    <div className={`inline-flex flex-col gap-0.5 px-3 py-1.5 rounded-xl border text-xs ${cfg.bg}`}>

      {/* Estimated remaining stock */}
      <div className={`flex items-center gap-1.5 font-semibold ${cfg.color}`}>
        <Icon size={12} />
        <span>
          {estRemaining <= 0
            ? "Stock likely finished — reorder now"
            : `~${estRemaining} ${unit} remaining`}
        </span>
      </div>

      {/* Days left + daily rate */}
      <div className="text-slate-500">
        {daysLeft !== null && daysLeft > 0
          ? `~${daysLeft} days left · `
          : ""}
        {rate.daily_rate} {unit}/day avg
        {rate.reorder_by && rate.status !== "ok" && (
          <span className="ml-1">
            · reorder by {new Date(rate.reorder_by + "T00:00:00")
              .toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
          </span>
        )}
      </div>

      {/* Low confidence warning */}
      {rate.confidence === "low" && (
        <div className="text-slate-400 text-[10px]">
          Based on {rate.data_points} purchases — estimate improves over time
        </div>
      )}
    </div>
  );
}

"""
AlertEngine — Detects consumption anomalies and generates actionable alerts.

Design Pattern: Chain of Responsibility + Open/Closed Principle
  - Each alert type is a separate Rule class
  - Add new alert types via AlertEngine.add_rule() — no existing code changes
  - Rules are evaluated in priority order

Current rules:
  1. SpikeRule       — today's usage > avg + 2×std_dev (unusual spike)
  2. IdleRule        — item sitting unused 2+ days (expiry risk)
  3. LowStockRule    — closing qty < 2 days of avg usage (reorder needed)

Future rules (just create and add_rule()):
  - WastageRule      — when recipe mapping available
  - CostSpikeRule    — when ingredient cost jumps
  - SeasonalRule     — weekend vs weekday patterns
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict
from dataclasses import dataclass, field

from services.inventory.analytics import ItemStats


# ── Alert Data Classes ─────────────────────────────────────────────────────

@dataclass
class Alert:
    """
    Immutable alert object. One per item per rule.
    severity: 'critical', 'warning', 'info'
    """
    item_id:    str
    item_name:  str
    unit:       str
    severity:   str          # critical / warning / info
    alert_type: str          # spike / idle / low_stock
    title:      str          # short heading shown in UI
    message:    str          # full human-readable message
    value:      float        # the triggering value (for display)
    threshold:  float        # the threshold that was crossed
    action:     str          # what to do about it
    meta:       dict = field(default_factory=dict)  # extra data for future use

    def to_dict(self) -> dict:
        return {
            "item_id":    self.item_id,
            "item_name":  self.item_name,
            "unit":       self.unit,
            "severity":   self.severity,
            "alert_type": self.alert_type,
            "title":      self.title,
            "message":    self.message,
            "value":      self.value,
            "threshold":  self.threshold,
            "action":     self.action,
            "meta":       self.meta,
        }


# ── Abstract Rule Base ─────────────────────────────────────────────────────

class AbstractAlertRule(ABC):
    """
    Base class for all alert rules.
    Implement evaluate() to return an Alert or None.
    """

    @property
    @abstractmethod
    def rule_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, stats: ItemStats, today_consumption: float) -> Alert | None:
        """
        Evaluate one item against this rule.
        Returns Alert if triggered, None if safe.
        """
        raise NotImplementedError


# ── Concrete Rules ─────────────────────────────────────────────────────────

class SpikeRule(AbstractAlertRule):
    """
    Triggers when today's consumption is significantly above normal.
    Formula: today > avg + (sensitivity × std_dev)

    sensitivity=2.0 means: flag if today is 2 standard deviations above average
    Lower sensitivity → more alerts. Higher → fewer but more significant alerts.
    """

    def __init__(self, sensitivity: float = 2.0, min_data_points: int = 7):
        self.sensitivity = sensitivity
        self.min_data_points = min_data_points

    @property
    def rule_name(self) -> str:
        return "spike"

    def evaluate(self, stats: ItemStats, today_consumption: float) -> Alert | None:
        # Need enough history to compute meaningful average
        if stats.data_points < self.min_data_points:
            return None
        if stats.avg_daily_usage == 0 or today_consumption == 0:
            return None

        threshold = stats.avg_daily_usage + (self.sensitivity * stats.std_deviation)
        if today_consumption <= threshold:
            return None

        excess = round(today_consumption - stats.avg_daily_usage, 3)
        excess_pct = round(excess / stats.avg_daily_usage * 100, 1)
        severity = "critical" if excess_pct > 50 else "warning"

        return Alert(
            item_id=stats.item_id,
            item_name=stats.item_name,
            unit=stats.unit,
            severity=severity,
            alert_type="spike",
            title=f"Unusual usage: {stats.item_name}",
            message=(
                f"{stats.item_name} consumed {today_consumption} {stats.unit} today — "
                f"{excess_pct}% above the {stats.avg_daily_usage} {stats.unit} daily average. "
                f"Check for spillage or wastage."
            ),
            value=today_consumption,
            threshold=round(threshold, 3),
            action="Check kitchen for spillage, over-portioning, or theft.",
            meta={"excess_kg": excess, "excess_pct": excess_pct,
                  "avg": stats.avg_daily_usage, "std_dev": stats.std_deviation},
        )


class IdleRule(AbstractAlertRule):
    """
    Triggers when closing qty has been unchanged for N consecutive days.
    Indicates item is sitting unused → expiry/spoilage risk.
    """

    def __init__(self, idle_days_threshold: int = 2):
        self.idle_days_threshold = idle_days_threshold

    @property
    def rule_name(self) -> str:
        return "idle"

    def evaluate(self, stats: ItemStats, today_consumption: float) -> Alert | None:
        if stats.days_idle < self.idle_days_threshold:
            return None
        if stats.current_closing_qty <= 0:
            return None

        severity = "critical" if stats.days_idle >= 3 else "warning"
        cost_at_risk = round(stats.current_closing_qty * stats.last_price, 2)

        return Alert(
            item_id=stats.item_id,
            item_name=stats.item_name,
            unit=stats.unit,
            severity=severity,
            alert_type="idle",
            title=f"Expiry risk: {stats.item_name}",
            message=(
                f"{stats.item_name} has been sitting at "
                f"{stats.current_closing_qty} {stats.unit} "
                f"for {stats.days_idle} days without being used. "
                f"Worth approximately ₹{cost_at_risk:.0f}."
            ),
            value=stats.current_closing_qty,
            threshold=float(self.idle_days_threshold),
            action=(
                f"Use {stats.item_name} in today's menu to avoid spoilage. "
                f"Consider a special dish featuring it."
            ),
            meta={"days_idle": stats.days_idle, "cost_at_risk": cost_at_risk},
        )


class LowStockRule(AbstractAlertRule):
    """
    Triggers when closing qty is below N days of average usage.
    Earlier and smarter than the existing reorder_level check.
    """

    def __init__(self, days_cover: float = 2.0):
        self.days_cover = days_cover

    @property
    def rule_name(self) -> str:
        return "low_stock"

    def evaluate(self, stats: ItemStats, today_consumption: float) -> Alert | None:
        if stats.avg_daily_usage == 0:
            return None

        safety_stock = round(stats.avg_daily_usage * self.days_cover, 3)
        if stats.current_closing_qty > safety_stock:
            return None

        days_left = round(
            stats.current_closing_qty / stats.avg_daily_usage, 1
        ) if stats.avg_daily_usage > 0 else 0

        recommended_order = round(
            (stats.avg_daily_usage * 3) - stats.current_closing_qty, 3
        )  # order 3 days worth minus what's left

        severity = "critical" if days_left < 1 else "warning"

        return Alert(
            item_id=stats.item_id,
            item_name=stats.item_name,
            unit=stats.unit,
            severity=severity,
            alert_type="low_stock",
            title=f"Low stock: {stats.item_name}",
            message=(
                f"Only {stats.current_closing_qty} {stats.unit} of {stats.item_name} remaining "
                f"— approximately {days_left} day(s) of stock at current usage rate."
            ),
            value=stats.current_closing_qty,
            threshold=safety_stock,
            action=f"Order approximately {recommended_order} {stats.unit} of {stats.item_name}.",
            meta={"days_left": days_left, "recommended_order": recommended_order,
                  "avg_daily_usage": stats.avg_daily_usage},
        )


# ── Alert Engine ───────────────────────────────────────────────────────────

class AlertEngine:
    """
    Evaluates all items against all rules.

    Open for extension via add_rule() — never need to modify this class.
    Rules are evaluated in order of severity (critical first).

    Usage:
        engine = AlertEngine()
        engine.add_rule(WastageRule())      # future
        alerts = await engine.evaluate_all(stats_map, consumptions)
    """

    SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

    def __init__(self):
        # Default rules — ordered by business priority
        self._rules: List[AbstractAlertRule] = [
            SpikeRule(sensitivity=2.0),
            IdleRule(idle_days_threshold=2),
            LowStockRule(days_cover=2.0),
        ]

    def add_rule(self, rule: AbstractAlertRule) -> "AlertEngine":
        """Add a new rule. Returns self for chaining."""
        self._rules.append(rule)
        return self

    def remove_rule(self, rule_name: str) -> "AlertEngine":
        """Remove a rule by name."""
        self._rules = [r for r in self._rules if r.rule_name != rule_name]
        return self

    def evaluate_all(
        self,
        stats_map: Dict[str, ItemStats],
        today_consumptions: Dict[str, float],
    ) -> List[Alert]:
        """
        Evaluate all items against all rules.
        Returns sorted list of alerts (critical first).
        """
        alerts: List[Alert] = []

        for item_id, stats in stats_map.items():
            today = today_consumptions.get(item_id, 0.0)
            for rule in self._rules:
                try:
                    alert = rule.evaluate(stats, today)
                    if alert:
                        alerts.append(alert)
                except Exception as e:
                    # Never let one bad item crash the whole engine
                    import logging
                    logging.warning(f"AlertEngine rule {rule.rule_name} failed for {item_id}: {e}")

        # Sort: critical first, then warning, then info
        alerts.sort(key=lambda a: self.SEVERITY_ORDER.get(a.severity, 99))
        return alerts

from dataclasses import dataclass
from math import isfinite, sqrt


@dataclass(frozen=True)
class AnomalyThresholds:
    """Tunable, deterministic thresholds for the read-only anomaly service."""

    baseline_days: int = 28
    min_history_points: int = 7
    z_score_min_points: int = 14
    z_score_threshold: float = 3.0
    high_severity_percent: float = 100.0
    order_volume_change_percent: float = 50.0
    revenue_change_percent: float = 50.0
    average_order_value_change_percent: float = 50.0
    cost_change_percent: float = 50.0
    marketing_spend_change_percent: float = 50.0
    marketing_rate_change_percent: float = 30.0
    cancellation_rate_change_points: float = 15.0
    min_delivered_orders_for_average: int = 3
    min_orders_for_cancellation_rate: int = 5
    min_units_for_product_contribution: int = 3
    min_delivered_orders_for_city: int = 3

    def __post_init__(self):
        positive_ints = (
            self.baseline_days,
            self.min_history_points,
            self.z_score_min_points,
            self.min_delivered_orders_for_average,
            self.min_orders_for_cancellation_rate,
            self.min_units_for_product_contribution,
            self.min_delivered_orders_for_city,
        )
        if any(value < 1 for value in positive_ints):
            raise ValueError("Anomaly threshold counts must be positive integers.")
        if self.min_history_points > self.baseline_days:
            raise ValueError("min_history_points cannot exceed baseline_days.")
        if not isfinite(self.z_score_threshold) or self.z_score_threshold <= 0:
            raise ValueError("z_score_threshold must be positive.")


class AnomalyDetectionEngine:

    # ===================================
    # DETECT ANOMALIES
    # ===================================

    @staticmethod
    def detect_spike(
        current_value: float,
        average_value: float
    ):

        if average_value <= 0:

            return False

        return (
            current_value >
            average_value * 2
        )

    @staticmethod
    def compare_with_history(
        observed_value: float,
        history: list[float],
        *,
        min_history_points: int,
        change_threshold_percent: float,
        z_score_min_points: int,
        z_score_threshold: float,
    ) -> dict | None:
        """Return an explainable deviation when enough positive baseline data exists."""
        clean = []
        for value in history:
            try:
                parsed = float(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if isfinite(parsed) and parsed >= 0:
                clean.append(parsed)
        observed = float(observed_value)
        if (
            not isfinite(observed)
            or observed < 0
            or len(clean) < min_history_points
        ):
            return None
        expected = sum(clean) / len(clean)
        if expected <= 0:
            return None
        absolute = observed - expected
        percent = absolute / expected * 100
        method = "historical_mean_percentage_change"
        z_score = None
        if len(clean) >= z_score_min_points:
            variance = sum((value - expected) ** 2 for value in clean) / len(clean)
            deviation = sqrt(variance)
            if deviation > 0:
                z_score = absolute / deviation
                method = "historical_mean_percentage_change_and_z_score"
        is_anomaly = abs(percent) >= change_threshold_percent
        if z_score is not None:
            is_anomaly = is_anomaly or abs(z_score) >= z_score_threshold
        if not is_anomaly:
            return None
        return {
            "expected_value": expected,
            "deviation_value": absolute,
            "deviation_percent": percent,
            "z_score": z_score,
            "method": method,
        }

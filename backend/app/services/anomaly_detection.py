import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def compute_stats(values: List[float]) -> Dict[str, float]:
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "ema": 0.0, "latest": 0.0, "min": 0.0, "max": 0.0}
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / max(1, n - 1) if n > 1 else 0.0
    std = math.sqrt(variance)
    alpha = 0.3
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1.0 - alpha) * ema
    return {
        "mean": round(mean, 3),
        "std": round(std, 3),
        "ema": round(ema, 3),
        "latest": round(values[-1], 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


class AnomalyDetectionService:
    """
    Explainable statistical anomaly detection using moving averages,
    exponential smoothing, rolling standard deviation, and threshold deviation.
    An anomaly is not automatically a confirmed network incident.
    """

    MIN_SAMPLES = 3

    @staticmethod
    def evaluate_metric_series(
        entity_type: str,
        entity_id: str,
        entity_name: str,
        metric_name: str,
        anomaly_type: str,
        values: List[float],
        timestamps: List[datetime],
        hard_warning: float,
        hard_critical: float,
        analysis_period_hours: int,
    ) -> Optional[Dict[str, Any]]:
        n = len(values)
        if n < AnomalyDetectionService.MIN_SAMPLES:
            return None

        stats = compute_stats(values)
        latest = stats["latest"]
        baseline_vals = values[:-1]
        base_stats = compute_stats(baseline_vals)
        z_score = (latest - base_stats["mean"]) / base_stats["std"] if base_stats["std"] > 0.01 else 0.0

        is_threshold = latest >= hard_warning
        is_statistical = z_score >= 2.2 and (latest - base_stats["mean"]) >= 5.0

        if not (is_threshold or is_statistical):
            return None

        severity = "CRITICAL" if latest >= hard_critical or z_score >= 3.5 else (
            "HIGH" if latest >= hard_warning else "MEDIUM"
        )
        confidence = min(98.0, round(60.0 + min(abs(z_score), 4.0) * 8.0 + (10.0 if is_threshold else 0.0), 1))

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "anomaly_type": anomaly_type,
            "metric_name": metric_name,
            "severity": severity,
            "observed_value": latest,
            "baseline_mean": base_stats["mean"],
            "rolling_std": base_stats["std"],
            "ema": stats["ema"],
            "z_score": round(z_score, 2),
            "threshold_warning": hard_warning,
            "is_confirmed_incident": False,
            "classification": "DETECTED",
            "data_source": "SIMULATION",
            "analysis_period_hours": analysis_period_hours,
            "sample_count": n,
            "last_sample_timestamp": timestamps[-1].isoformat() if timestamps else None,
            "forecast_horizon_minutes": 0,
            "confidence": confidence,
            "evidence": (
                f"{metric_name} observed at {latest} vs baseline mean {base_stats['mean']} "
                f"(std={base_stats['std']}, z={round(z_score, 2)})."
            ),
        }

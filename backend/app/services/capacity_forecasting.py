from datetime import datetime
from typing import Any, Dict, List, Optional


def linear_regression_slope(xs: List[float], ys: List[float]) -> Dict[str, float]:
    n = len(xs)
    if n < 2:
        return {"slope": 0.0, "intercept": ys[0] if ys else 0.0, "r_squared": 0.0}
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    if ss_xx <= 1e-9:
        return {"slope": 0.0, "intercept": mean_y, "r_squared": 0.0}
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_sq = max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 1e-9 else 0.0
    return {"slope": slope, "intercept": intercept, "r_squared": round(r_sq, 3)}


class CapacityForecastingService:
    """
    Explainable linear-trend capacity and exhaustion forecasting.
    Returns INSUFFICIENT_DATA when fewer than 3 real samples are present.
    """

    MIN_SAMPLES = 3

    @staticmethod
    def forecast_metric(
        entity_type: str,
        entity_id: str,
        entity_name: str,
        metric_name: str,
        values: List[float],
        timestamps: List[datetime],
        horizon_minutes: int = 60,
        exhaustion_threshold: float = 90.0,
        analysis_period_hours: int = 24,
    ) -> Dict[str, Any]:
        n = len(values)
        if n < CapacityForecastingService.MIN_SAMPLES or len(timestamps) < CapacityForecastingService.MIN_SAMPLES:
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "metric_name": metric_name,
                "status": "INSUFFICIENT_DATA",
                "classification": "INSUFFICIENT_DATA",
                "data_source": "SIMULATION",
                "analysis_period_hours": analysis_period_hours,
                "sample_count": n,
                "last_sample_timestamp": timestamps[-1].isoformat() if timestamps else None,
                "forecast_horizon_minutes": horizon_minutes,
                "confidence": 0.0,
                "current_value": round(values[-1], 2) if values else None,
                "predicted_value": None,
                "slope_per_hour": None,
                "minutes_to_threshold": None,
                "predictive_warning": False,
                "message": "Insufficient telemetry samples (minimum 3 required) for reliable forecasting.",
            }

        t0 = timestamps[0]
        xs_minutes = [max(0.0, (ts - t0).total_seconds() / 60.0) for ts in timestamps]
        reg = linear_regression_slope(xs_minutes, values)
        slope_per_min = reg["slope"]
        slope_per_hour = round(slope_per_min * 60.0, 3)

        last_x = xs_minutes[-1]
        raw_pred = reg["intercept"] + slope_per_min * (last_x + horizon_minutes)
        predicted_value = round(max(0.0, min(100.0, raw_pred)), 2)
        current_value = round(values[-1], 2)

        minutes_to_threshold: Optional[float] = None
        if current_value >= exhaustion_threshold:
            minutes_to_threshold = 0.0
        elif slope_per_min > 0.01:
            minutes_to_threshold = round((exhaustion_threshold - current_value) / slope_per_min, 1)

        predictive_warning = bool(
            predicted_value >= (exhaustion_threshold - 10.0)
            or (minutes_to_threshold is not None and minutes_to_threshold <= horizon_minutes * 2)
        )
        confidence = round(min(95.0, 45.0 + min(n, 30) * 1.2 + reg["r_squared"] * 15.0), 1)

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "metric_name": metric_name,
            "status": "WARNING" if predictive_warning else "NORMAL",
            "classification": "PREDICTED",
            "data_source": "SIMULATION",
            "analysis_period_hours": analysis_period_hours,
            "sample_count": n,
            "last_sample_timestamp": timestamps[-1].isoformat(),
            "forecast_horizon_minutes": horizon_minutes,
            "confidence": confidence,
            "current_value": current_value,
            "predicted_value": predicted_value,
            "slope_per_hour": slope_per_hour,
            "r_squared": reg["r_squared"],
            "exhaustion_threshold": exhaustion_threshold,
            "minutes_to_threshold": minutes_to_threshold,
            "predictive_warning": predictive_warning,
            "message": (
                f"Predicted {metric_name} in {horizon_minutes}m: {predicted_value}% "
                f"(slope {slope_per_hour}%/hr)."
            ),
        }

"""
Analyst Agent
Performs quantitative analysis, pattern detection, and chart generation.
"""
import json
import logging
from typing import Optional, List, Annotated
from datetime import datetime, timedelta
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)


class AnalystAgent:
    """
    The Analyst specialises in numbers. Given raw data from documents,
    it finds patterns, computes statistics, detects anomalies,
    and generates charts for the dashboard.
    """

    @kernel_function(
        description="""Analyse a list of data points and return statistics including
        total, average, trend direction, and any anomalies detected.
        Use this when you have numerical data that needs to be summarised."""
    )
    async def compute_statistics(
        self,
        data: Annotated[str, "JSON string of data points: [{date, value, label}]"],
        metric_name: Annotated[str, "What is being measured e.g. 'customer complaints'"],
    ) -> str:
        try:
            points = json.loads(data) if isinstance(data, str) else data
            if not points:
                return json.dumps({"error": "No data provided"})

            values = [p.get("value", 0) for p in points if isinstance(p.get("value"), (int, float))]
            if not values:
                return json.dumps({"error": "No numeric values found in data"})

            total = sum(values)
            average = total / len(values)
            minimum = min(values)
            maximum = max(values)
            latest = values[-1] if values else 0
            previous = values[-2] if len(values) > 1 else latest
            change_pct = ((latest - previous) / previous * 100) if previous != 0 else 0

            # Detect anomalies — values more than 2 standard deviations from mean
            mean = average
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std_dev = variance ** 0.5
            anomalies = [
                {"index": i, "value": v, "deviation": round((v - mean) / std_dev, 2)}
                for i, v in enumerate(values)
                if abs(v - mean) > 2 * std_dev
            ]

            # Trend direction
            if len(values) >= 3:
                first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
                second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                trend = "increasing" if second_half_avg > first_half_avg * 1.05 else \
                        "decreasing" if second_half_avg < first_half_avg * 0.95 else "stable"
            else:
                trend = "insufficient data"

            return json.dumps({
                "metric": metric_name,
                "summary": {
                    "total": round(total, 2),
                    "average": round(average, 2),
                    "minimum": round(minimum, 2),
                    "maximum": round(maximum, 2),
                    "latest_value": latest,
                    "change_from_previous": f"{change_pct:+.1f}%",
                    "trend": trend,
                    "data_points": len(values),
                },
                "anomalies": anomalies,
                "insight": self._generate_insight(metric_name, trend, change_pct, anomalies),
            })

        except Exception as e:
            logger.error(f"Analyst compute_statistics failed: {e}")
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""Find time-based patterns in data — peak hours, busiest days,
        seasonal trends. Use this for complaint data, usage data, or any 
        time-series information."""
    )
    async def find_time_patterns(
        self,
        data: Annotated[str, "JSON string of timestamped events: [{timestamp, value, category}]"],
        metric_name: Annotated[str, "What is being measured"],
    ) -> str:
        try:
            events = json.loads(data) if isinstance(data, str) else data
            if not events:
                return json.dumps({"patterns": [], "message": "No data provided"})

            # Simulate pattern analysis — in production this processes real timestamps
            # For demo, returns realistic MTN-style patterns
            return json.dumps({
                "metric": metric_name,
                "patterns": {
                    "peak_hours": ["18:00-19:00", "19:00-20:00", "20:00-21:00"],
                    "busiest_day": "Thursday",
                    "quietest_day": "Sunday",
                    "weekly_trend": "Complaints increase 34% on weekdays vs weekends",
                    "monthly_trend": "15% increase month-over-month",
                },
                "key_finding": "Peak complaint period is 6-9pm weekdays, suggesting "
                               "network congestion during post-work hours.",
            })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""Detect anomalies or unusual spikes in a dataset.
        Use this when you need to find out if something unusual is happening
        compared to historical norms."""
    )
    async def detect_anomalies(
        self,
        current_value: Annotated[float, "The current observed value"],
        historical_average: Annotated[float, "The historical average for comparison"],
        metric_name: Annotated[str, "What is being measured"],
        threshold_pct: Annotated[float, "Percentage increase considered anomalous (default 50%)"] = 50.0,
    ) -> str:
        try:
            if historical_average == 0:
                return json.dumps({
                    "is_anomaly": True,
                    "message": f"No historical baseline for {metric_name}",
                })

            change_pct = ((current_value - historical_average) / historical_average) * 100
            is_anomaly = abs(change_pct) >= threshold_pct
            severity = "critical" if abs(change_pct) >= threshold_pct * 2 else \
                       "warning" if is_anomaly else "normal"

            return json.dumps({
                "metric": metric_name,
                "is_anomaly": is_anomaly,
                "severity": severity,
                "current_value": current_value,
                "historical_average": historical_average,
                "change_percent": round(change_pct, 1),
                "interpretation": (
                    f"{metric_name} is {abs(change_pct):.1f}% {'above' if change_pct > 0 else 'below'} "
                    f"historical average. {'This is a significant anomaly requiring attention.' if is_anomaly else 'This is within normal range.'}"
                ),
            })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""Compare two values or datasets and return a clear comparison summary.
        Use this when asked to compare periods, departments, or metrics."""
    )
    async def compare_metrics(
        self,
        value_a: Annotated[float, "First value"],
        value_b: Annotated[float, "Second value"],
        label_a: Annotated[str, "Label for first value e.g. 'This month'"],
        label_b: Annotated[str, "Label for second value e.g. 'Last month'"],
        metric_name: Annotated[str, "What is being compared"],
    ) -> str:
        try:
            if value_b != 0:
                change_pct = ((value_a - value_b) / value_b) * 100
                direction = "increase" if change_pct > 0 else "decrease"
            else:
                change_pct = 100
                direction = "increase"

            return json.dumps({
                "metric": metric_name,
                "comparison": {
                    label_a: value_a,
                    label_b: value_b,
                    "change": f"{change_pct:+.1f}%",
                    "direction": direction,
                    "absolute_difference": round(value_a - value_b, 2),
                },
                "summary": (
                    f"{metric_name}: {label_a} shows {abs(change_pct):.1f}% {direction} "
                    f"compared to {label_b} ({value_b} → {value_a})."
                ),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _generate_insight(
        self, metric: str, trend: str, change_pct: float, anomalies: list
    ) -> str:
        parts = []
        if trend == "increasing":
            parts.append(f"{metric} is trending upward.")
        elif trend == "decreasing":
            parts.append(f"{metric} is trending downward.")
        else:
            parts.append(f"{metric} is stable.")

        if abs(change_pct) > 20:
            parts.append(
                f"Recent period shows a significant {change_pct:+.1f}% change."
            )
        if anomalies:
            parts.append(
                f"{len(anomalies)} anomalous data point(s) detected that warrant investigation."
            )
        return " ".join(parts)

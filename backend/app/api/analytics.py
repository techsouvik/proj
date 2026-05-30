import logging
import json
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.api.ingest import redis_conn

logger = logging.getLogger("AnalyticsAPI")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("")
def get_metrics(db: Session = Depends(get_db)):
    """
    Computes real-time telemetry metrics and returns structured payload
    to drive the SVG dashboard visuals in the frontend.
    """
    cache_key = "aether_analytics_metrics"
    if redis_conn is not None:
        try:
            cached_data = redis_conn.get(cache_key)
            if cached_data:
                logger.info("Serving analytics metrics from Redis cache.")
                return json.loads(cached_data)
        except Exception as ce:
            logger.warning(f"Failed to read from Redis cache: {ce}")

    try:
        # 1. Base query counts
        total_logs = db.query(models.InferenceLog).count()
        
        if total_logs == 0:
            # Return empty/default telemetry payload if database is pristine
            return {
                "summary": {
                    "total_requests": 0,
                    "success_rate": 100.0,
                    "avg_latency_ms": 0.0,
                    "total_tokens": 0,
                    "error_rate": 0.0
                },
                "latency_distribution": {"under_500ms": 0, "between_500ms_1s": 0, "between_1s_2s": 0, "over_2s": 0},
                "model_shares": [],
                "throughput_timeline": [],
                "recent_errors": []
            }

        # 2. General Performance Aggregates
        success_count = db.query(models.InferenceLog).filter(models.InferenceLog.status == "success").count()
        cancelled_count = db.query(models.InferenceLog).filter(models.InferenceLog.status == "cancelled").count()
        error_count = db.query(models.InferenceLog).filter(models.InferenceLog.status == "error").count()
        
        success_rate = (success_count / total_logs) * 100 if total_logs > 0 else 100.0
        error_rate = (error_count / total_logs) * 100 if total_logs > 0 else 0.0

        avg_latency = db.query(func.avg(models.InferenceLog.latency_ms)).scalar() or 0.0
        total_tokens = db.query(func.sum(models.InferenceLog.total_tokens)).scalar() or 0

        # 3. Model & Provider distribution
        model_query = db.query(
            models.InferenceLog.model,
            models.InferenceLog.provider,
            func.count(models.InferenceLog.id).label("count"),
            func.sum(models.InferenceLog.total_tokens).label("tokens")
        ).group_by(models.InferenceLog.model, models.InferenceLog.provider).all()

        model_shares = []
        for mq in model_query:
            model_shares.append({
                "model": mq.model,
                "provider": mq.provider,
                "requests": mq.count,
                "tokens": mq.tokens or 0
            })

        # 4. Latency Distribution Bands
        under_500ms = db.query(models.InferenceLog).filter(models.InferenceLog.latency_ms < 500).count()
        b_500_1000 = db.query(models.InferenceLog).filter(models.InferenceLog.latency_ms >= 500, models.InferenceLog.latency_ms < 1000).count()
        b_1000_2000 = db.query(models.InferenceLog).filter(models.InferenceLog.latency_ms >= 1000, models.InferenceLog.latency_ms < 2000).count()
        over_2000 = db.query(models.InferenceLog).filter(models.InferenceLog.latency_ms >= 2000).count()

        latency_distribution = {
            "under_500ms": under_500ms,
            "between_500ms_1s": b_500_1000,
            "between_1s_2s": b_1000_2000,
            "over_2s": over_2000
        }

        # 5. Database-Agnostic Hourly Throughput / Latency Timeline (Python grouped)
        # Fetch the last 200 logs to formulate a detailed recent history timeline
        recent_logs = db.query(
            models.InferenceLog.timestamp,
            models.InferenceLog.latency_ms,
            models.InferenceLog.total_tokens,
            models.InferenceLog.status
        ).order_by(models.InferenceLog.timestamp.desc()).limit(200).all()

        # Sort chronological
        recent_logs = list(reversed(recent_logs))

        # Group by 1-minute intervals to draw a smooth real-time SVG chart in the UI
        timeline_buckets = defaultdict(lambda: {"count": 0, "total_latency": 0.0, "total_tokens": 0, "errors": 0})
        
        for log in recent_logs:
            # Format to Minute (e.g. "14:35")
            time_str = log.timestamp.strftime("%H:%M")
            timeline_buckets[time_str]["count"] += 1
            timeline_buckets[time_str]["total_latency"] += log.latency_ms
            timeline_buckets[time_str]["total_tokens"] += log.total_tokens
            if log.status == "error":
                timeline_buckets[time_str]["errors"] += 1

        throughput_timeline = []
        for time_key, b in timeline_buckets.items():
            throughput_timeline.append({
                "time": time_key,
                "requests": b["count"],
                "avg_latency_ms": round(b["total_latency"] / b["count"], 2),
                "tokens": b["total_tokens"],
                "errors": b["errors"]
            })

        # Keep only the last 15 active intervals to fit nicely on the frontend graph
        throughput_timeline = throughput_timeline[-15:]

        # 6. Retrieve recent errors to audit failure modes
        error_logs = db.query(
            models.InferenceLog.timestamp,
            models.InferenceLog.model,
            models.InferenceLog.error_message
        ).filter(models.InferenceLog.status == "error").order_by(models.InferenceLog.timestamp.desc()).limit(10).all()

        recent_errors = []
        for err in error_logs:
            recent_errors.append({
                "timestamp": err.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "model": err.model,
                "error": err.error_message or "Unknown execution error."
            })

        metrics_payload = {
            "summary": {
                "total_requests": total_logs,
                "success_rate": round(success_rate, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "total_tokens": total_tokens,
                "error_rate": round(error_rate, 2),
                "cancelled_requests": cancelled_count
            },
            "latency_distribution": latency_distribution,
            "model_shares": model_shares,
            "throughput_timeline": throughput_timeline,
            "recent_errors": recent_errors
        }

        # Cache compiled metrics in Redis with a 10s TTL
        if redis_conn is not None:
            try:
                redis_conn.setex(cache_key, 10, json.dumps(metrics_payload))
                logger.info("Successfully cached compiled analytics metrics in Redis (TTL=10s).")
            except Exception as ce:
                logger.warning(f"Failed to cache compiled metrics to Redis: {ce}")

        return metrics_payload

    except Exception as e:
        logger.error(f"Failed to generate telemetry dashboard metrics: {e}")
        return {"error": "Internal database metrics computation error."}

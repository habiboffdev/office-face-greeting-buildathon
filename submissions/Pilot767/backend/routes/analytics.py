from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from database import get_connection
from models import AnalyticsSummary

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()

    with get_connection() as conn:
        visitors_today = conn.execute(
            "SELECT COUNT(DISTINCT person_id) FROM visits WHERE visited_at >= ?",
            (today_start,),
        ).fetchone()[0]

        visits_week = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE visited_at >= ?",
            (week_start,),
        ).fetchone()[0]

        recent = conn.execute(
            """
            SELECT p.full_name, v.visited_at
            FROM visits v
            JOIN people p ON p.id = v.person_id
            ORDER BY v.visited_at DESC
            LIMIT 8
            """
        ).fetchall()

        frequent = conn.execute(
            """
            SELECT full_name, total_visits
            FROM people
            WHERE total_visits > 0
            ORDER BY total_visits DESC
            LIMIT 5
            """
        ).fetchall()

        peak = conn.execute(
            """
            SELECT strftime('%H', visited_at) as hour, COUNT(*) as count
            FROM visits
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 6
            """
        ).fetchall()

    return AnalyticsSummary(
        visitors_today=visitors_today,
        visits_this_week=visits_week,
        recent_visitors=[
            {"full_name": r["full_name"], "visited_at": r["visited_at"]} for r in recent
        ],
        frequent_visitors=[
            {"full_name": r["full_name"], "total_visits": r["total_visits"]}
            for r in frequent
        ],
        peak_hours=[{"hour": r["hour"], "count": r["count"]} for r in peak],
    )

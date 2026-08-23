from fastapi import HTTPException

from app.models.summary import ItemsSummary
from genesis import analytics, router

api = router("/analytics")


@api.get("/items-summary", response_model=ItemsSummary)
def items_summary():
    try:
        rows = analytics.query(
            "SELECT CAST(created_at AS DATE) AS day, count(*) AS count "
            "FROM pg.public.items GROUP BY 1 ORDER BY 1 DESC"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Analytics error: {exc}") from exc
    return {"total": sum(row["count"] for row in rows), "by_day": rows}

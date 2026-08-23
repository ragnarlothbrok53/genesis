from datetime import date

from pydantic import BaseModel


class DayCount(BaseModel):
    day: date
    count: int


class ItemsSummary(BaseModel):
    total: int
    by_day: list[DayCount]

from pydantic import BaseModel


class VipUpdate(BaseModel):
    is_vip: bool


class BirthdayUpdate(BaseModel):
    birthday: str | None = None


class PersonCreate(BaseModel):
    full_name: str
    is_vip: bool = False
    birthday: str | None = None


class PersonResponse(BaseModel):
    id: int
    full_name: str
    image_path: str
    total_visits: int
    last_seen_at: str | None
    is_vip: bool
    birthday: str | None
    created_at: str


class VisitResponse(BaseModel):
    id: int
    person_id: int
    full_name: str
    visited_at: str


class VideoResponse(BaseModel):
    id: int
    filename: str
    title: str | None
    url: str


class WelcomeEvent(BaseModel):
    person_id: int
    full_name: str
    greeting: str
    is_vip: bool = False


class AnalyticsSummary(BaseModel):
    visitors_today: int
    visits_this_week: int
    recent_visitors: list[dict]
    frequent_visitors: list[dict]
    peak_hours: list[dict]

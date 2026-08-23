from pydantic import BaseModel, Field


class JobStart(BaseModel):
    seconds: int = Field(default=3, ge=0, le=60)


class JobStatus(BaseModel):
    workflow_id: str
    status: str
    result: str | None = None

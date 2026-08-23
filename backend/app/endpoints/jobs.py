from fastapi import HTTPException

from app.models.job import JobStart, JobStatus
from app.tasks.demo import demo_sleep
from genesis import jobs, router

api = router("/jobs")


@api.post("", response_model=JobStatus, status_code=201)
async def start_job(payload: JobStart):
    job_id = await jobs.run_task(demo_sleep, payload.seconds)
    return {"workflow_id": job_id, "status": "RUNNING", "result": None}


@api.get("/{workflow_id}", response_model=JobStatus)
async def get_job(workflow_id: str):
    status = await jobs.job_status(workflow_id)
    if status["status"] == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=f"No job '{workflow_id}'")
    return status

from fastapi import HTTPException

from app.models.chat import ChatRequest, ChatResponse
from genesis import ai, router

api = router("/ai")


@api.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        reply = ai.chat(payload.prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc
    return {"reply": reply}


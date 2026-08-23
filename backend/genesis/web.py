from fastapi import APIRouter


def router(prefix: str = "", tags: list[str] | None = None) -> APIRouter:
    clean = prefix.strip("/")
    return APIRouter(
        prefix=f"/{clean}" if clean else "",
        tags=tags or ([clean] if clean else None),
    )

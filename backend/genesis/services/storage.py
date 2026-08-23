import logging
from pathlib import Path

from genesis.core.config import settings

logger = logging.getLogger(__name__)

_filesystems: dict[str, object] = {}


def _s3() -> bool:
    return settings.STORAGE_BACKEND == "s3"


def _local_path() -> Path:
    path = Path(settings.get("STORAGE_LOCAL_PATH", "/data/storage"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _s3_bucket() -> str:
    bucket = settings.get("STORAGE_S3_BUCKET")
    if not bucket:
        raise RuntimeError(
            "S3 storage not configured; set STORAGE_S3_BUCKET in .env "
            "(or switch STORAGE_BACKEND to local)"
        )
    return bucket


def _filesystem():
    import fsspec

    if "s3" not in _filesystems:
        _filesystems["s3"] = fsspec.filesystem(
            "s3",
            endpoint_url=settings.get("STORAGE_S3_ENDPOINT") or None,
            key=settings.get("STORAGE_S3_ACCESS_KEY") or None,
            secret=settings.get("STORAGE_S3_SECRET_KEY") or None,
        )
    return _filesystems["s3"]


def check() -> bool:
    try:
        if _s3():
            _filesystem().exists(_s3_bucket())
            return True
        _local_path()
        return True
    except Exception:
        return False


def save(key: str, data: bytes) -> None:
    if _s3():
        with _filesystem().open(f"{_s3_bucket()}/{key}", "wb") as handle:
            handle.write(data)
        return
    path = _local_path() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get(key: str) -> bytes:
    if _s3():
        remote_path = f"{_s3_bucket()}/{key}"
        if not _filesystem().exists(remote_path):
            raise FileNotFoundError(f"storage key not found: {key}")
        with _filesystem().open(remote_path, "rb") as handle:
            return handle.read()
    path = _local_path() / key
    if not path.is_file():
        raise FileNotFoundError(f"storage key not found: {key}")
    return path.read_bytes()


def delete(key: str) -> None:
    if _s3():
        remote_path = f"{_s3_bucket()}/{key}"
        if _filesystem().exists(remote_path):
            _filesystem().rm(remote_path)
        return
    path = _local_path() / key
    path.unlink(missing_ok=True)


def url(key: str) -> str:
    if _s3():
        endpoint = settings.get("STORAGE_S3_ENDPOINT") or ""
        return f"{endpoint.rstrip('/')}/{_s3_bucket()}/{key}"
    return (_local_path() / key).as_uri()

import httpx
from app.config import settings


def _filer_url(object_name: str) -> str:
    """Build full SeaweedFS Filer URL for a given object path."""
    base = settings.SEAWEEDFS_FILER_URL.rstrip("/")
    return f"{base}/{object_name}"


def upload_file(object_name: str, file_bytes: bytes, content_type: str = "application/octet-stream") -> str:
    """Uploads bytes to SeaweedFS Filer and returns the object name."""
    url = _filer_url(object_name)
    # SeaweedFS Filer accepts multipart file upload via POST
    files = {"file": (object_name.split("/")[-1], file_bytes, content_type)}
    response = httpx.post(url, files=files, timeout=60.0)
    response.raise_for_status()
    return object_name


def get_file_bytes(object_name: str) -> bytes:
    """Downloads a file from SeaweedFS Filer and returns its bytes."""
    url = _filer_url(object_name)
    response = httpx.get(url, timeout=60.0)
    if response.status_code == 404:
        raise Exception(f"File not found in SeaweedFS: {object_name}")
    response.raise_for_status()
    return response.content


def delete_file(object_name: str) -> bool:
    """Deletes a file from SeaweedFS Filer."""
    url = _filer_url(object_name)
    try:
        response = httpx.delete(url, timeout=30.0)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error deleting object from SeaweedFS: {e}")
        return False

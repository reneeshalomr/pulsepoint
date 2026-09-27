from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/api/audio", tags=["audio"])
AUDIO_DIR = Path(__file__).resolve().parents[2] / "static" / "audio"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    ".webm": {"audio/webm", "video/webm", "application/octet-stream"},
    ".mp3": {"audio/mpeg", "audio/mp3", "application/octet-stream"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "application/octet-stream"},
}
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


@router.post("")
async def upload_audio(file: UploadFile = File(...)) -> dict:
    extension = Path(file.filename or "").suffix.casefold()
    if extension not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio type")
    content_type = (file.content_type or "application/octet-stream").casefold()
    if content_type not in ALLOWED_AUDIO_TYPES[extension]:
        raise HTTPException(status_code=415, detail="Audio content type does not match file extension")
    content = await file.read(MAX_AUDIO_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=422, detail="Audio file is empty")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds 10 MB limit")
    filename = f"{uuid4().hex}{extension}"
    (AUDIO_DIR / filename).write_bytes(content)
    return {"audio_url": f"/static/audio/{filename}", "content_type": content_type,
            "size_bytes": len(content)}

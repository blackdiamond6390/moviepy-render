# main.py – FastAPI-Backend mit CORS, MoviePy & explizitem Preflight für /render

import os
import uuid
import tempfile
import requests
from io import BytesIO

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, vfx

# ─── 1) FastAPI-Instanz ────────────────────────────────────────────────
app = FastAPI()

# ─── 2) Preflight-Handler für CORS auf /render ─────────────────────────
@app.options("/render")
async def preflight_render() -> Response:
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )

# ─── 3) Globale CORS-Middleware ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # oder ["https://creator.zerowork.io"]
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ─── 4) Statische Auslieferung ───────────────────────────────────────────
TMP_DIR = tempfile.gettempdir()   # Render: /tmp
app.mount("/static", StaticFiles(directory=TMP_DIR), name="static")

# ─── 5) Bild-URL → ImageClip Helfer ────────────────────────────────────
def image_url_to_clip(url: str, duration: float = 3.0) -> ImageClip:
    """Lädt ein Bild von URL, wandelt es in einen MoviePy-Clip um."""
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(400, f"Failed to download image: {url} ({exc})")

    from PIL import Image
    import numpy as np

    img = Image.open(BytesIO(resp.content)).convert("RGB")
    frame = np.array(img)
    return ImageClip(frame).set_duration(duration)

# ─── 6) POST /render Endpoint ──────────────────────────────────────────
@app.post("/render")
async def render_video(req: Request):
    data = await req.json()
    images = data.get("images")
    if not images:
        raise HTTPException(400, "'images' list is missing")

    # 6.1) ImageClips bauen
    clips = []
    for entry in images:
        if isinstance(entry, str):
            url, dur = entry, 3.0
        elif isinstance(entry, dict):
            url = entry.get("url")
            dur = float(entry.get("duration", 3.0))
        else:
            raise HTTPException(400, f"Invalid image entry: {entry}")
        clips.append(image_url_to_clip(url, dur))

    # 6.2) 0.5 s Cross-Fade zwischen den Clips
    video = concatenate_videoclips(
        clips,
        method="compose",
        padding=-0.5,
        transition=vfx.fadein(clips[0], 0.5)
    )

    # 6.3) Optionale Hintergrund-Musik
    if data.get("audio"):
        audio_clip = AudioFileClip(data["audio"]).subclip(0, video.duration)
        video = video.set_audio(audio_clip.volumex(0.4))

    # 6.4) Video in TMP_DIR schreiben
    outname = f"video_{uuid.uuid4().hex[:8]}.mp4"
    outpath = os.path.join(TMP_DIR, outname)
    video.write_videofile(
        outpath,
        fps=data.get("fps", 24),
        codec=data.get("codec", "libx264"),
        audio_codec="aac",
        threads=4,
        logger=None
    )
    video.close()

    # 6.5) Download-URL zurückgeben
    return {"url": f"/static/{outname}"}

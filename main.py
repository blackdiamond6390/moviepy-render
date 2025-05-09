# main.py – FastAPI-Backend mit CORS & MoviePy 1.0.3

import os
import uuid
import tempfile
import requests
from io import BytesIO

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, vfx

# ─── 1) FastAPI + CORS ────────────────────────────────────────────────
TMP_DIR = tempfile.gettempdir()
app = FastAPI()

# Erlaube Cross-Origin für alle Domains, Methoden und Header
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # <- hier beliebige Domains oder ["*"]
    allow_methods=["*"],       # GET, POST, OPTIONS, …
    allow_headers=["*"],       # Content-Type, Authorization, …
    allow_credentials=True
)

# Statische Dateien (fertige Videos) unter /static serven
app.mount("/static", StaticFiles(directory=TMP_DIR), name="static")


# ─── 2) Hilfs-Funktion: lädt Bild-URL und gibt ImageClip zurück ────────
def image_url_to_clip(url: str, duration: float = 3.0) -> ImageClip:
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


# ─── 3) POST /render – verarbeitet dein JSON und baut das Video ───────
@app.post("/render")
async def render_video(req: Request):
    data = await req.json()
    images = data.get("images")
    if not images or not isinstance(images, list):
        raise HTTPException(400, "'images' list is missing")

    # 1) ImageClips bauen
    clips = []
    for entry in images:
        if isinstance(entry, dict):
            url = entry.get("url")
            dur = float(entry.get("duration", 3))
        else:
            raise HTTPException(400, f"Invalid image entry: {entry}")
        clips.append(image_url_to_clip(url, dur))

    # 2) 0.5 s Cross-Fade zwischen allen Clips
    video = concatenate_videoclips(
        clips,
        method="compose",
        padding=-0.5,
        transition=vfx.fadein(clips[0], 0.5)
    )

    # 3) optionale Hintergrund-Musik
    if data.get("audio"):
        audio_clip = AudioFileClip(data["audio"]).subclip(0, video.duration)
        video = video.set_audio(audio_clip.volumex(0.4))

    # 4) fertiges Video schreiben
    outname = f"video_{uuid.uuid4().hex[:8]}.mp4"
    outpath = os.path.join(TMP_DIR, outname)
    video.write_videofile(
        outpath,
        fps=int(data.get("fps", 24)),
        codec=data.get("codec", "libx264"),
        audio_codec="aac",
        threads=4,
        logger=None
    )
    video.close()

    # 5) URL zurückliefern
    return {"url": f"/static/{outname}"}

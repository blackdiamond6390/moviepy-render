# main.py  –  FastAPI‑Backend mit MoviePy 1.0.3
# * holt HTTP‑Bilder runter
# * baut ImageClips (3 s default)
# * verbindet sie mit 0.5 s Cross‑Fade
# * optional Background‑Musik
# * legt fertige MP4 im OS‑Temp‑Ordner ab und liefert die URL zurück

import os, uuid, tempfile, requests
from io import BytesIO

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles

from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips, vfx
)

TMP_DIR = tempfile.gettempdir()              # /tmp auf Render
app = FastAPI()
app.mount("/static", StaticFiles(directory=TMP_DIR), name="static")

# ---------- Hilfs‑Funktion --------------------------------------------------
def image_url_to_clip(url: str, duration: float = 3.0) -> ImageClip:
    """lädt ein Bild von einer URL und gibt einen MoviePy‑ImageClip zurück"""
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(400, f"Failed to download image: {url} ({exc})")
    # Pillow → NumPy Array → ImageClip
    from PIL import Image
    import numpy as np

    img = Image.open(BytesIO(resp.content)).convert("RGB")
    frame = np.array(img)
    return ImageClip(frame).set_duration(duration)

# ---------- API‑Endpoint ----------------------------------------------------
@app.post("/render")
async def render_video(req: Request):
    """
    JSON‑Schema:
    {
      "images": [
        "https://.../a.jpg",
        {"url":"https://.../b.jpg", "duration":4}
      ],
      "audio": "https://.../track.mp3"   # optional
    }
    """
    data = await req.json()
    images = data.get("images")
    if not images:
        raise HTTPException(400, "'images' list is missing")

    # 1) ImageClips bauen -----------------------------------------------
    clips = []
    for entry in images:
        if isinstance(entry, str):
            url, dur = entry, 3
        elif isinstance(entry, dict):
            url = entry.get("url")
            dur = float(entry.get("duration", 3))
        else:
            raise HTTPException(400, f"Invalid image entry: {entry}")
        clips.append(image_url_to_clip(url, dur))

    # 0.5 s Cross‑Fade zwischen Clips
    video = concatenate_videoclips(
        clips,
        method="compose",
        padding=-0.5,
        transition=vfx.fadein(clips[0], 0.5)   # fade‑Objekt
    )

    # 2) optional Audio ---------------------------------------------------
    if data.get("audio"):
        audio_clip = AudioFileClip(data["audio"]).subclip(0, video.duration)
        video = video.set_audio(audio_clip.volumex(0.4))

    # 3) Video schreiben --------------------------------------------------
    outname = f"video_{uuid.uuid4().hex[:8]}.mp4"
    outpath = os.path.join(TMP_DIR, outname)
    video.write_videofile(
        outpath,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None
    )
    video.close()

    return {"url": f"/static/{outname}"}

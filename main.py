# main.py  –  FastAPI‑Backend mit MoviePy
# =======================================
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from moviepy.editor import *
import uuid, os, tempfile

app = FastAPI()

# --------------------------------------------------
#  Static-Files-Mount, damit /static/video_*.mp4 abrufbar ist
# --------------------------------------------------
tmp_dir = tempfile.gettempdir()           # z. B. /tmp bei Linux / /var/folders/… bei macOS
app.mount("/static", StaticFiles(directory=tmp_dir), name="static")

# --------------------------------------------------
#  POST /render  –  erwartet JSON:
#     {
#       "images": ["https://url1.jpg", "..."],
#       "audio": "https://musik.mp3"          (optional)
#     }
#  Liefert: { "url": "/static/video_abc123.mp4" }
# --------------------------------------------------
@app.post("/render")
async def render_video(req: Request):
    data   = await req.json()
    images = data["images"]                # Liste Bild-URLs oder lokale Pfade
    music  = data.get("audio")             # Background-Musik (optional)

    # ---- 1. Bilder in Clips verwandeln (je 3 s) ----
    clips = [ImageClip(img).set_duration(3) for img in images]
    video = concatenate_videoclips(clips, method="compose")   # verbindet alle Clips

    # ---- 2. Musik unterlegen (falls vorhanden) ----
    if music:
        song  = AudioFileClip(music).subclip(0, video.duration)
        video = video.set_audio(song.volumex(0.4))            # Musik leiser (40 %)

    # ---- 3. Video-Datei erzeugen ----
    outname = f"video_{uuid.uuid4().hex[:8]}.mp4"
    outpath = os.path.join(tmp_dir, outname)

    video.write_videofile(
        outpath,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4
    )

    # ---- 4. URL zurückgeben ----
    return {"url": f"/static/{outname}"}

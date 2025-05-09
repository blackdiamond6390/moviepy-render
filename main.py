from fastapi import FastAPI, Request
from moviepy.editor import *
import uuid, os, tempfile

app = FastAPI()

@app.post("/render")
async def render_video(req: Request):
    data   = await req.json()             # erwartet {"images":[...], "audio":"..."}
    images = data["images"]               # Bild‑Links oder ‑Dateinamen
    music  = data.get("audio")            # Hintergrundmusik (optional)

    clips = [ImageClip(img).set_duration(3) for img in images]
    video = concatenate_videoclips(clips, method="compose")

    if music:
        song  = AudioFileClip(music).subclip(0, video.duration)
        video = video.set_audio(song.volumex(0.4))  # Musik leiser

    outname = f"video_{uuid.uuid4().hex[:6]}.mp4"
    outpath = os.path.join(tempfile.gettempdir(), outname)
    video.write_videofile(outpath, fps=24, codec="libx264", audio_codec="aac")

    return {"url": f"/static/{outname}"}  # Link zum fertigen Video zurückgeben

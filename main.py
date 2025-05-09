from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from moviepy.editor import *
import uuid, os, tempfile

app = FastAPI()

TMP_DIR = tempfile.gettempdir()
app.mount("/static", StaticFiles(directory=TMP_DIR), name="static")

def build_clip(entry, default_duration=3):
    if isinstance(entry, str):
        url, dur = entry, default_duration
    elif isinstance(entry, dict) and "url" in entry:
        url, dur = entry["url"], float(entry.get("duration", default_duration))
    else:
        raise ValueError("Wrong image entry")
    return ImageClip(url).set_duration(dur)

@app.post("/render")
async def render_video(req: Request):
    data = await req.json()
    if not data.get("images"):
        raise HTTPException(400, "'images' list missing")

    clips = [build_clip(e) for e in data["images"]]
    video = concatenate_videoclips(clips, method="compose")

    if data.get("audio"):
        bgm = AudioFileClip(data["audio"]).subclip(0, video.duration)
        video = video.set_audio(bgm.volumex(0.4))

    name = f"video_{uuid.uuid4().hex[:8]}.mp4"
    path = os.path.join(TMP_DIR, name)
    video.write_videofile(path, fps=24,
                          codec="libx264", audio_codec="aac",
                          threads=4, logger=None)
    video.close()
    return {"url": f"/static/{name}"}

import os
import subprocess
import shutil
import re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[^\w\s\-\.]', '', name)
    return cleaned.strip() or "track"

@app.get("/")
def read_root():
    return {"status": "ATMOS Backend active"}

@app.post("/process-audio")
async def process_audio(
    file: UploadFile = File(...),
    speed: float = Form(1.0),
    reverb: float = Form(0.0),
    bass: float = Form(0.0),
    is_8d: str = Form("false"),
    vocal_remover: str = Form("false"),
    eq: str = Form("+2,-3,-3,0,0,+2,+5,+7,+8"),
    bitrate: str = Form("320k"),
    custom_title: str = Form("Track (BStrack)")
):
    safe_title = sanitize_filename(custom_title)
    input_path = f"temp_input_{safe_title}.mp3"
    output_path = f"processed_{safe_title}.mp3"

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Simplest FFmpeg test with high compatibility
        audio_filters = []

        if vocal_remover.lower() == "true":
            audio_filters.append("pan=stereo|c0=c0-c1|c1=c1-c0")

        if speed != 1.0:
            audio_filters.append(f"atempo={speed}")

        if is_8d.lower() == "true":
            audio_filters.append("apulsator=hz=0.08,volume=1.35")

        if reverb > 0:
            r_val = min(max(reverb / 100.0, 0.1), 1.0)
            audio_filters.append(f"aecho=0.8:0.88:60:{r_val}")

        filter_str = ",".join(audio_filters) if audio_filters else "anull"

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", filter_str,
            "-b:a", bitrate,
            output_path
        ]

        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if process.returncode != 0:
            err_msg = process.stderr[-300:] if process.stderr else "FFmpeg bajarishda noaniq xatolik"
            raise Exception(f"FFmpeg Error: {err_msg}")

        if os.path.exists(input_path):
            os.remove(input_path)

        return FileResponse(output_path, media_type="audio/mpeg", filename=f"{safe_title}.mp3")

    except Exception as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        # Haqiqiy xatolikni HTTP 500 orqali frontendga uzatamiz
        raise HTTPException(status_code=500, detail=str(e))

import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydub import AudioSegment

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "Atmos Remaker API ishlayapti!"}

@app.post("/process-audio")
async def process_audio(
    file: UploadFile = File(...),
    speed: float = Form(1.0),
    reverb: float = Form(0.0),
    bass: float = Form(0.0)
):
    try:
        temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_in.write(await file.read())
        temp_in.close()

        audio = AudioSegment.from_file(temp_in.name)

        if speed != 1.0 and speed > 0:
            audio = audio._spawn(audio.raw_data, overrides={
                "frame_rate": int(audio.frame_rate * speed)
            }).set_frame_rate(audio.frame_rate)

        if bass > 0:
            gain_db = (bass / 100.0) * 6.0
            lows = audio.low_pass_filter(150).apply_gain(gain_db)
            audio = audio.overlay(lows)

        if reverb > 0:
            delay_ms = int(50 + (reverb / 100.0) * 150)
            decay = 0.3 + (reverb / 100.0) * 0.4
            echo = audio.silent(duration=delay_ms) + (audio - int(decay * 10))
            audio = audio.overlay(echo)

        temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_out.close()
        audio.export(temp_out.name, format="mp3")

        os.remove(temp_in.name)

        return FileResponse(
            temp_out.name,
            media_type="audio/mpeg",
            filename=f"processed_{file.filename}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

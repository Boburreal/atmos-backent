import os
import subprocess
import shutil
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
    eq: str = Form("+2,-4,-4,0,0,+2,+5,+7,+8"),
    bitrate: str = Form("320k"),
    custom_title: str = Form("Track (BStrack)")
):
    input_path = f"temp_{file.filename}"
    output_path = f"processed_{custom_title}.mp3"

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        filters = []

        # 1. Vocal Remover (Artist ovozini o'chirish / Instrumental)
        if vocal_remover.lower() == "true":
            # Center Channel Inversion + Vocal Band Stop
            filters.append("pan=stereo|c0=c0-c1|c1=c1-c0,equalizer=f=1000:width_type=h:width=2000:g=-15")

        # 2. Speed (Atempo)
        if speed != 1.0:
            filters.append(f"atempo={speed}")

        # 3. Bass va Equalizer
        eq_vals = [float(x) for x in eq.split(",")]
        if len(eq_vals) == 9:
            filters.append(
                f"equalizer=f=64:width_type=h:width=200:g={eq_vals[0]+(bass/10)},"
                f"equalizer=f=160:width_type=h:width=200:g={eq_vals[1]},"
                f"equalizer=f=400:width_type=h:width=200:g={eq_vals[2]},"
                f"equalizer=f=1000:width_type=h:width=200:g={eq_vals[3]},"
                f"equalizer=f=2500:width_type=h:width=200:g={eq_vals[4]},"
                f"equalizer=f=6250:width_type=h:width=200:g={eq_vals[5]},"
                f"equalizer=f=12500:width_type=h:width=200:g={eq_vals[6]},"
                f"equalizer=f=16000:width_type=h:width=200:g={eq_vals[7]}"
            )

        # 4. Reverb
        if reverb > 0:
            out_g = 0.88 * (reverb / 100)
            filters.append(f"aecho=0.8:{out_g}:60:0.4")

        # 5. 8D Audio (Aylanish tezligi sekinlashtirildi: hz=0.08)
        if is_8d.lower() == "true":
            filters.append("apulsator=hz=0.08")

        filter_complex = ",".join(filters) if filters else "anull"

        # FFmpeg Buyrug'i
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path]
        
        has_cover = os.path.exists("cover.jpg")
        if has_cover:
            ffmpeg_cmd.extend(["-i", "cover.jpg"])

        ffmpeg_cmd.extend(["-af", filter_complex])

        # Asl rasmni o'chirib, o'rniga yangi cover.jpg rasmini majburiy (override) qo'yish
        if has_cover:
            ffmpeg_cmd.extend([
                "-map", "0:a", 
                "-map", "1:v", 
                "-c:v", "mjpeg", 
                "-disposition:v:0", "attached_pic",
                "-id3v2_version", "3"
            ])

        ffmpeg_cmd.extend([
            "-b:a", bitrate,
            "-metadata", f"title={custom_title}",
            "-metadata", "artist=BStrack Studio",
            output_path
        ])

        subprocess.run(ffmpeg_cmd, check=True)

        if os.path.exists(input_path):
            os.remove(input_path)

        return FileResponse(output_path, media_type="audio/mpeg", filename=f"{custom_title}.mp3")

    except Exception as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise HTTPException(status_code=500, detail=str(e))

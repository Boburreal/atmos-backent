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
    eq: str = Form("+2,-3,-3,0,0,+2,+5,+7,+8"),
    bitrate: str = Form("320k"),
    custom_title: str = Form("Track (BStrack)")
):
    input_path = f"temp_{file.filename}"
    output_path = f"processed_{custom_title}.mp3"

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        filters = []

        # 1. Vocal Remover
        if vocal_remover.lower() == "true":
            filters.append("pan=stereo|c0=c0-c1|c1=c1-c0,equalizer=f=1000:width_type=h:width=3000:g=-24,superequalizer=1b=1:2b=1:3b=1:4b=0:5b=-10:6b=-10:7b=-10:8b=0:9b=1")

        # 2. Speed (Atempo)
        if speed != 1.0:
            filters.append(f"atempo={speed}")

        # 3. Bass va Equalizer
        eq_vals = [float(x) for x in eq.split(",")]
        if len(eq_vals) == 9:
            extra_bass = (bass / 10)
            filters.append(
                f"equalizer=f=50:width_type=h:width=100:g={eq_vals[0]+extra_bass},"
                f"equalizer=f=100:width_type=h:width=150:g={eq_vals[1]+(extra_bass*0.7)},"
                f"equalizer=f=250:width_type=h:width=200:g={eq_vals[2]},"
                f"equalizer=f=600:width_type=h:width=300:g={eq_vals[3]},"
                f"equalizer=f=1500:width_type=h:width=500:g={eq_vals[4]},"
                f"equalizer=f=4000:width_type=h:width=1000:g={eq_vals[5]},"
                f"equalizer=f=8000:width_type=h:width=2000:g={eq_vals[6]},"
                f"equalizer=f=12000:width_type=h:width=3000:g={eq_vals[7]},"
                f"equalizer=f=16000:width_type=h:width=4000:g={eq_vals[8]}"
            )

        # 4. MUKAMMAL HQ STUDIO REVERB (Multi-Stage Stereo Space Reverb)
        if reverb > 0:
            # Reverb kuchini foizga mos ravishda aniq hisoblash
            r_ratio = reverb / 100.0  # 0.0 dan 1.0 gacha
            
            # Aks-sado qaytish vaqtlari (ms) va intensivlik ko'rsatkichlari
            d1 = int(35 + r_ratio * 45)    # Early reflections
            d2 = int(70 + r_ratio * 75)    # Late reflections
            d3 = int(120 + r_ratio * 110)  # Hall tail
            
            decay1 = round(0.25 + r_ratio * 0.45, 2)
            decay2 = round(0.18 + r_ratio * 0.38, 2)
            decay3 = round(0.10 + r_ratio * 0.30, 2)
            
            # Stereo reverb chain: aks-sado yuqori va pastki shovqinlarni tozalash (lowpass/highpass) va keng spatial sado
            reverb_filter = (
                f"aecho=0.85:0.88:{d1}|{d2}|{d3}:{decay1}|{decay2}|{decay3},"
                f"highpass=f=80,"
                f"lowpass=f=11000"
            )
            filters.append(reverb_filter)

        # 5. 8D Audio (Pan Effect)
        if is_8d.lower() == "true":
            filters.append("apulsator=hz=0.08,volume=1.35")

        filter_complex = ",".join(filters) if filters else "anull"

        # FFmpeg buyrug'i
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path]
        
        has_cover = os.path.exists("cover.jpg")
        if has_cover:
            ffmpeg_cmd.extend(["-i", "cover.jpg"])

        ffmpeg_cmd.extend(["-af", filter_complex])

        # Cover image biriktirish
        if has_cover:
            ffmpeg_cmd.extend([
                "-map", "0:a", 
                "-map", "1:v", 
                "-c:v", "mjpeg", 
                "-disposition:v:0", "attached_pic",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (BStrack)",
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

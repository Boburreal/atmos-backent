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

        # Boshlang'ich filterlar ro'yxati
        audio_filters = []

        # 1. Vocal Remover
        if vocal_remover.lower() == "true":
            audio_filters.append("pan=stereo|c0=c0-c1|c1=c1-c0,equalizer=f=1000:width_type=h:width=3000:g=-24,superequalizer=1b=1:2b=1:3b=1:4b=0:5b=-10:6b=-10:7b=-10:8b=0:9b=1")

        # 2. Speed (Atempo)
        if speed != 1.0:
            audio_filters.append(f"atempo={speed}")

        # 3. Bass va Equalizer
        eq_vals = [float(x) for x in eq.split(",")]
        if len(eq_vals) == 9:
            extra_bass = (bass / 10)
            audio_filters.append(
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

        # 4. MUKAMMAL HQ REVERB (Echo-siz, toza studio space)
        if reverb > 0:
            # Reverb miqdorini hisoblash (50% bo'lganda juda mukammal va toza zal effekti beradi)
            r_val = reverb / 100.0
            
            # Reverb parametri: room_size (zal kattaligi), damp (yutilish), wet (reverb ovozi)
            room = round(0.3 + r_val * 0.55, 2)       # 0.3 dan 0.85 gacha
            damp = round(0.2 + (1.0 - r_val) * 0.5, 2) # Yuqori chastotali g'ovlamani yo'qotish
            wet_vol = round(r_val * 0.5, 2)            # Wet signal kuchi
            
            # Asl ovozni saqlagan holda orqaga toza reverb qatlami qo'shiladi
            reverb_chain = (
                f"asplit[dry][to_rev];"
                f"[to_rev]freeverb=roomscale={room}:damping={damp}:wetlevel=1.0:drylevel=0.0:width=1.0,"
                f"highpass=f=120,lowpass=f=10000,volume={wet_vol}[wet];"
                f"[dry][wet]amix=inputs=2:weights=1.0 1.0:dropout_transition=0"
            )
            audio_filters.append(reverb_chain)

        # 5. 8D Audio
        if is_8d.lower() == "true":
            audio_filters.append("apulsator=hz=0.08,volume=1.35")

        filter_complex_str = ",".join(audio_filters) if audio_filters else "anull"

        # FFmpeg buyrug'i
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path]
        
        has_cover = os.path.exists("cover.jpg")
        if has_cover:
            ffmpeg_cmd.extend(["-i", "cover.jpg"])

        ffmpeg_cmd.extend(["-filter_complex", f"[0:a]{filter_complex_str}[outa]", "-map", "[outa]"])

        # Album cover biriktirish
        if has_cover:
            ffmpeg_cmd.extend([
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

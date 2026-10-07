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
        # 1. Yuklangan faylni saqlash
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        audio_filters = []

        # 2. Vocal Remover (agar yoqilgan bo'lsa)
        if vocal_remover.lower() == "true":
            audio_filters.append("pan=stereo|c0=c0-c1|c1=c1-c0")

        # 3. Tezlik (Speed)
        if speed != 1.0:
            audio_filters.append(f"atempo={speed}")

        # 4. ai-audio-editor saytidagi aniq 9-polosali EQ sozlamalari
        # 60Hz(+2), 170Hz(-3), 310Hz(-3), 600Hz(0), 1k(0), 3k(+2), 6k(+5), 12k(+7), 16k(+8)
        try:
            eq_vals = [float(x) for x in eq.split(",")]
            if len(eq_vals) == 9:
                extra_bass = (bass / 10.0)
                audio_filters.append(
                    f"equalizer=f=60:width_type=h:width=50:g={eq_vals[0] + extra_bass},"
                    f"equalizer=f=170:width_type=h:width=100:g={eq_vals[1]},"
                    f"equalizer=f=310:width_type=h:width=200:g={eq_vals[2]},"
                    f"equalizer=f=600:width_type=h:width=300:g={eq_vals[3]},"
                    f"equalizer=f=1000:width_type=h:width=500:g={eq_vals[4]},"
                    f"equalizer=f=3000:width_type=h:width=1000:g={eq_vals[5]},"
                    f"equalizer=f=6000:width_type=h:width=2000:g={eq_vals[6]},"
                    f"equalizer=f=12000:width_type=h:width=3000:g={eq_vals[7]},"
                    f"equalizer=f=16000:width_type=h:width=4000:g={eq_vals[8]}"
                )
        except Exception:
            pass

        # 5. 8D Audio
        if is_8d.lower() == "true":
            audio_filters.append("apulsator=hz=0.08,volume=1.35")

        # 6. slowedandreverb.studio saytidagi kabi 45% Reverb effekti
        if reverb > 0:
            r_val = min(max(reverb / 100.0, 0.05), 1.0)
            audio_filters.append(f"aecho=0.8:0.88:60:{r_val}")

        filter_str = ",".join(audio_filters) if audio_filters else "anull"

        # 7. Oblozka faylini avtomatik topish
        cover_path = None
        for possible_name in ["cover.jpg", "cover.jpg.jpg", "cover.png", "cover.jpeg"]:
            if os.path.exists(possible_name):
                cover_path = possible_name
                break

        # 8. FFmpeg buyrug'ini tayyorlash
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path]

        if cover_path:
            ffmpeg_cmd.extend(["-i", cover_path])

        ffmpeg_cmd.extend(["-af", filter_str])

        # Oblozkani AIMP va Telegram pleyerlariga to'g'ri o'tkazish
        if cover_path:
            ffmpeg_cmd.extend([
                "-map", "0:a",
                "-map", "1:v",
                "-c:v", "copy",
                "-disposition:v:0", "attached_pic",
                "-id3v2_version", "3"
            ])

        ffmpeg_cmd.extend([
            "-b:a", bitrate,
            "-metadata", f"title={custom_title}",
            "-metadata", "artist=BStrack",
            output_path
        ])

        # 9. FFmpeg ni bajarish
        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if process.returncode != 0:
            err_msg = process.stderr[-300:] if process.stderr else "FFmpeg bajarishda xatolik"
            raise Exception(f"FFmpeg Error: {err_msg}")

        if os.path.exists(input_path):
            os.remove(input_path)

        return FileResponse(output_path, media_type="audio/mpeg", filename=f"{safe_title}.mp3")

    except Exception as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise HTTPException(status_code=500, detail=str(e))

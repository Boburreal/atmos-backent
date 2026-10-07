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
    reverb: float = Form(45.0), # Standart reverb darajasi 45% ga oshirildi
    bass: float = Form(0.0),
    is_8d: str = Form("false"),
    vocal_remover: str = Form("false"),
    eq: str = Form("+2,-3,-3,0,0,+2,+5,+7,+8"),
    bitrate: str = Form("320k"),
    custom_title: str = Form("") # BStrack avtomatik qo'shilishi olib tashlandi
):
    # Agar nom berilmagan bo'lsa, asl fayl nomini olish
    base_name = os.path.splitext(file.filename)[0] if file.filename else "track"
    final_title = custom_title.strip() if custom_title.strip() else base_name
    
    safe_title = sanitize_filename(final_title)
    input_path = f"temp_input_{safe_title}.mp3"
    output_path = f"processed_{safe_title}.mp3"

    try:
        # 1. Yuklangan faylni saqlash
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        audio_filters = []

        # 2. Vocal Remover
        if vocal_remover.lower() == "true":
            audio_filters.append("pan=stereo|c0=c0-c1|c1=c1-c0")

        # 3. Speed (Tezlik)
        if speed != 1.0:
            audio_filters.append(f"atempo={speed}")

        # 4. 9-polosali EQ (Saytdagidek aniq balans)
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

        # 6. Chuqur va hajmli Reverb (Saytdagi 45% effekti bilan bir xil)
        if reverb > 0:
            audio_filters.append("aecho=0.8:0.88:60:0.45")

        filter_str = ",".join(audio_filters) if audio_filters else "anull"

        # 7. Cover faylini izlash
        cover_path = None
        for possible_name in ["cover.jpg", "cover.png", "cover.jpeg"]:
            if os.path.exists(possible_name):
                cover_path = possible_name
                break

        # 8. FFmpeg buyrug'i
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path]

        if cover_path:
            ffmpeg_cmd.extend(["-i", cover_path])

        ffmpeg_cmd.extend(["-af", filter_str])

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
            "-metadata", f"title={final_title}",
            output_path
        ])

        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if process.returncode != 0:
            err_msg = process.stderr[-300:] if process.stderr else "FFmpeg xatoligi"
            raise Exception(f"FFmpeg Error: {err_msg}")

        if os.path.exists(input_path):
            os.remove(input_path)

        return FileResponse(output_path, media_type="audio/mpeg", filename=f"{safe_title}.mp3")

    except Exception as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise HTTPException(status_code=500, detail=str(e))

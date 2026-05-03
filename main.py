from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from agent import analyze_im_chat
from html_slides import generate_slide_deck
from ppt_tool import render_html_slides_to_ppt
from schemas import AnalyzeResponse, ChatRequest

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
WEB_UI_PATH = BASE_DIR / "web_ui.html"

app = FastAPI()
OUTPUT_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home():
    return WEB_UI_PATH.read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"message": "IM assistant is running."}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_chat(req: ChatRequest):
    job_id = uuid4().hex[:12]
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    try:
        analysis = analyze_im_chat(req.chat_text)
        deck_dir = OUTPUT_DIR / f"deck_{job_id}"
        deck = generate_slide_deck(analysis, str(deck_dir), generated_at)

        ppt_filename = f"im_report_{job_id}.pptx"
        ppt_path = OUTPUT_DIR / ppt_filename
        render_html_slides_to_ppt([str(path) for path in deck.slide_files], str(ppt_path))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    return {
        "analysis": analysis,
        "ppt_file": ppt_filename,
        "ppt_download_url": f"/download/{ppt_filename}",
        "slides_preview_url": f"/slides/{deck_dir.name}/index.html",
        "generated_at": generated_at,
    }


@app.get("/slides/{deck_name}/{file_name}", response_class=HTMLResponse)
def preview_slides(deck_name: str, file_name: str):
    deck_dir = _resolve_output_dir(deck_name)
    target_file = (deck_dir / Path(file_name).name).resolve()
    if deck_dir.resolve() not in target_file.parents or not target_file.exists():
        raise HTTPException(status_code=404, detail="Slide preview file not found.")
    return target_file.read_text(encoding="utf-8")


@app.get("/download/{filename}")
def download_ppt(filename: str):
    file_path = _resolve_output_file(filename)
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


def _resolve_output_file(filename: str) -> Path:
    safe_name = Path(filename).name
    file_path = OUTPUT_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PPT file not found.")
    return file_path


def _resolve_output_dir(deck_name: str) -> Path:
    safe_name = Path(deck_name).name
    deck_dir = OUTPUT_DIR / safe_name
    if not deck_dir.exists() or not deck_dir.is_dir():
        raise HTTPException(status_code=404, detail="Slide deck not found.")
    return deck_dir

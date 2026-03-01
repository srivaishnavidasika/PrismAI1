from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.services.pipeline import run_pipeline
from app.schemas import CodeRequest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.post("/run")
def run(request: CodeRequest):
    return run_pipeline(
        code=request.code,
        language=request.language,
        mode=request.mode,
        user_query=request.user_query,
        user_id=request.user_id,
        intent=request.intent,
    )

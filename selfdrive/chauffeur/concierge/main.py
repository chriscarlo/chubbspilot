#!/usr/bin/env python3
"""
Launch with:
    python -m selfdrive.chauffeur.concierge.main --dev      (auto-reload)
or
    uvicorn selfdrive.chauffeur.concierge.main:app --host 0.0.0.0 --port 5055
"""

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from cereal import messaging  # already on the device

BASE = Path(__file__).resolve().parent
templates = Environment(
    loader=FileSystemLoader(BASE / "templates"),
    autoescape=select_autoescape()
)

# ──────────────────── FastAPI app ──────────────────────
app = FastAPI(title="Concierge", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

# background task: poll SubMaster every N ms and keep latest snapshot in RAM
STATUS = {}

WANTED = ["deviceState", "carState", "thermal"]
available = [s for s in WANTED if s in messaging.SERVICE_LIST]

async def _status_poller() -> None:
    sm = messaging.SubMaster(available)
    while True:
        sm.update(0)
        snapshot = {"time": sm.frame}
        if "deviceState" in available:
            snapshot["deviceState"] = sm["deviceState"].to_dict()
        if "carState" in available:
            snapshot["carState"] = sm["carState"].to_dict()
        if "thermal" in available:
            snapshot["thermal"] = sm["thermal"].to_dict()
        STATUS.update(snapshot)
        await asyncio.sleep(0.25)


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(_status_poller())


# routes
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> str:
    tmpl = templates.get_template("index.html")
    return tmpl.render(request=request)


@app.get("/api/status")
async def api_status() -> dict:
    return STATUS


@app.get("/stream/sse")
async def stream_status() -> StreamingResponse:
    async def event_source() -> AsyncGenerator[str, None]:
        last_frame = -1
        while True:
            frame = STATUS.get("time", -1)
            if frame != last_frame:
                last_frame = frame
                yield f"data: {json.dumps(STATUS)}\n\n"
            await asyncio.sleep(0.25)
    return StreamingResponse(event_source(), media_type="text/event-stream")
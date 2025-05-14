#!/usr/bin/env python3
"""
Launch with:
    python -m selfdrive.chauffeur.concierge.main --dev      (auto-reload)
or
    uvicorn selfdrive.chauffeur.concierge.main:app --host 0.0.0.0 --port 5055
"""

import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator, Dict, List
from contextlib import asynccontextmanager
import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from cereal import messaging  # already on the device

# Set CRASH_LOGS_DIR to the actual path on the device
CRASH_LOGS_DIR = Path("/data/crashes")

BASE = Path(__file__).resolve().parent
templates = Environment(
    loader=FileSystemLoader(BASE / "templates"),
    autoescape=select_autoescape()
)

# background task: poll SubMaster every N ms and keep latest snapshot in RAM
STATUS = {}
POLLER_TASK = None

WANTED = ["deviceState", "carState", "thermal", "liveLocationKalman"]
available = [s for s in WANTED if s in messaging.SERVICE_LIST]

async def _status_poller() -> None:
    sm = messaging.SubMaster(available)
    try:
        while True:
            sm.update(0)
            snapshot = {"time": sm.frame}
            if "deviceState" in available:
                snapshot["deviceState"] = sm["deviceState"].to_dict()
            if "carState" in available:
                snapshot["carState"] = sm["carState"].to_dict()
            if "thermal" in available:
                snapshot["thermal"] = sm["thermal"].to_dict()
            if "liveLocationKalman" in available:
                snapshot["liveLocationKalman"] = sm["liveLocationKalman"].to_dict()
            STATUS.update(snapshot)
            await asyncio.sleep(0.25)
    except asyncio.CancelledError:
        print("Status poller cancelled.")
    except Exception as e:
        print(f"Error in status poller: {e}")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    global POLLER_TASK
    print("Concierge starting up...")
    POLLER_TASK = asyncio.create_task(_status_poller())
    yield
    print("Concierge shutting down...")
    if POLLER_TASK:
        POLLER_TASK.cancel()
        try:
            await POLLER_TASK
        except asyncio.CancelledError:
            print("Poller task successfully cancelled on shutdown.")

# ──────────────────── FastAPI app ──────────────────────
app = FastAPI(title="Concierge", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

# routes
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    tmpl = templates.get_template("index.html")
    # For the main page, page_title_text is empty as base.html already has "The Concierge"
    # browser_title_suffix can be empty or specific like "Dashboard"
    return tmpl.render(request=request, browser_title_suffix="- Dashboard", page_title_text="")


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


# Basic placeholder pages for our tiles
@app.get("/navigation", response_class=HTMLResponse)
async def navigation_page(request: Request):
    tmpl = templates.get_template("navigation.html")
    return tmpl.render(request=request, browser_title_suffix="- Navigation", page_title_text="- Navigation")

@app.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request):
    tmpl = templates.get_template("diagnostics.html")
    return tmpl.render(request=request, browser_title_suffix="- Diagnostics", page_title_text="- Diagnostics")

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    # tmpl = templates.get_template("logs.html")
    # return tmpl.render(request=request, browser_title_suffix="- Logs", page_title_text="- Logs")
    return "<h1>Logs Page</h1><p>Under Construction</p><a href='/'>Back to Dashboard</a>"

@app.get("/drive-data", response_class=HTMLResponse)
async def drive_data_page(request: Request):
    # tmpl = templates.get_template("drive_data.html")
    # return tmpl.render(request=request, browser_title_suffix="- Drive Data", page_title_text="- Drive Data")
    return "<h1>Drive Data Page</h1><p>Under Construction</p><a href='/'>Back to Dashboard</a>"

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    # tmpl = templates.get_template("test.html")
    # return tmpl.render(request=request, browser_title_suffix="- Test", page_title_text="- Test")
    return "<h1>Test Page</h1><p>Under Construction</p><a href='/'>Back to Dashboard</a>"

# New endpoints for crash logs
@app.get("/api/crash-logs")
async def list_crash_logs() -> List[Dict[str, str]]:
    """Returns a list of crash log files."""
    try:
        if not CRASH_LOGS_DIR.exists():
            return []

        log_files = []
        for file in CRASH_LOGS_DIR.glob("*.txt"):
            log_files.append({
                "name": file.name,
                "size": f"{file.stat().st_size / 1024:.1f} KB",
                "date": datetime.datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: datetime.datetime.strptime(x["date"], "%Y-%m-%d %H:%M:%S"), reverse=True)
        return log_files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing crash logs: {str(e)}")

@app.get("/api/crash-logs/{filename}")
async def get_crash_log(filename: str) -> PlainTextResponse:
    """Returns the content of a specific crash log file."""
    file_path = CRASH_LOGS_DIR / filename

    # Security check to prevent directory traversal
    if not file_path.is_relative_to(CRASH_LOGS_DIR) or not file_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        with open(file_path, "r") as f:
            return PlainTextResponse(f.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

def main():
    # This function is called by manager.py
    import uvicorn
    app_module_path = "selfdrive.chauffeur.concierge.main:app"
    uvicorn.run(app_module_path,
                host="0.0.0.0",
                port=5055,
                log_level="info")

if __name__ == "__main__":
    import uvicorn
    # This allows the script to be run directly with `python -m selfdrive.chauffeur.concierge.main`
    # and be started by the systemd service file in the same manner.
    # The --reload flag is typically for development, so we omit it here for a service context.
    # Uvicorn will pick up the `app` instance from this file.
    # MODIFIED: Use a fully qualified path for the app for robustness
    app_module_path = "selfdrive.chauffeur.concierge.main:app"

    # Check for --dev flag for reload functionality
    import sys
    should_reload = "--dev" in sys.argv

    uvicorn.run(app_module_path,
                host="0.0.0.0",
                port=5055,
                log_level="info",
                reload=should_reload,
                reload_dirs=["selfdrive/chauffeur/concierge"] if should_reload else None)
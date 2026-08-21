"""Application entrypoint.

Everything runs locally: SQLite on disk, OCR models on the CPU, no outbound
calls. That is a deliberate constraint rather than a shortcut -- the documents
this handles carry identity numbers, and the deployment target is a shared
kiosk or a Common Service Centre desktop with unreliable connectivity.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGIN_REGEX
from .db import init_db
from .routers import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Haq - Paperwork and Access",
    description=(
        "Reads government documents, works out which schemes a person qualifies for, "
        "explains the answer in their language, and fills in the form."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://haq-paperwork-access.vercel.app",
        "http://localhost:3010",]
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logging.getLogger(__name__).info("database ready")


@app.get("/")
def root() -> dict:
    return {"name": "Haq", "docs": "/docs", "api": "/api/health"}

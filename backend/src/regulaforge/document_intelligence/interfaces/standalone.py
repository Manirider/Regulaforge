"""
Standalone ASGI application for the Document Intelligence service.

Usage:
    uvicorn regulaforge.document_intelligence.interfaces.standalone:app
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from regulaforge.document_intelligence.interfaces.api import router

app = FastAPI(
    title="RegulaForge Document Intelligence Service",
    description="Document processing, OCR, NER, clause detection, and analysis",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

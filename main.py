"""
MTN Atlas — AI-Powered Enterprise Document Intelligence Platform
================================================================
Finalist solution for TeKnowledge × Microsoft 2026 Agentic AI Hackathon
Problem Statement: MTN Nigeria — Productivity & Workflow Management

Built by Team 4 | AI Lead: Ndubuisi Ekeh
Stack: FastAPI + Semantic Kernel + Azure OpenAI + Azure AI Search
"""

from dotenv import load_dotenv
load_dotenv()

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routes
from routes.auth import router as auth_router
from routes.ask import router as ask_router
from routes.documents import router as documents_router
from routes.alerts import router as alerts_router
from routes.analytics import router as analytics_router

# Database
from models.database import init_db

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="MTN Atlas",
    description="AI-powered enterprise document intelligence for MTN Nigeria. "
                "Multi-agent system built on Azure OpenAI + Microsoft Semantic Kernel.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ──────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(ask_router)
app.include_router(documents_router)
app.include_router(alerts_router)
app.include_router(analytics_router)

# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "MTN Atlas Backend",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    return {
        "name": "MTN Atlas",
        "description": "AI-powered enterprise document intelligence",
        "docs": "/docs",
        "health": "/health",
    }

# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("MTN Atlas starting up...")

    # Initialise database
    init_db()
    logger.info("Database initialised.")

    # Create default admin if no users exist
    from models.database import SessionLocal, User
    from services.auth_utils import hash_password, generate_api_key

    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            admin = User(
                email="admin@mtn.ng",
                hashed_password=hash_password("AtlasAdmin2026!"),
                full_name="MTN Atlas Admin",
                organisation="MTN Nigeria",
                department="Technology",
                role="admin",
                api_key=generate_api_key(),
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin created: admin@mtn.ng / AtlasAdmin2026!")
    finally:
        db.close()

    logger.info("MTN Atlas ready.")
    logger.info(f"Docs: http://localhost:8000/docs")

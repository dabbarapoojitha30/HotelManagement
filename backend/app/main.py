"""
VV Residency Hotel Management API — Application entry point.
FastAPI application with lifespan management, middleware, and exception handlers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import (
    connect_to_mongo,
    close_mongo_connection,
    get_user_collection,
    get_room_collection,
    get_booking_collection,
    create_indexes,
)
from app.routes import auth, rooms, bookings, dashboard
from app.utils.security import get_password_hash
from app.middleware.logging import RequestLoggingMiddleware
from app.core.exceptions import register_exception_handlers
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("VVResidencyAPI")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — connect to DB and create indexes on startup."""
    # Startup
    logger.info(f"SMTP_SERVER  Loaded: {bool(settings.SMTP_SERVER)}")
    logger.info(f"SMTP_USERNAME Loaded: {bool(settings.SMTP_USERNAME)}")
    logger.info(f"SMTP_PASSWORD Loaded: {bool(settings.SMTP_PASSWORD)}")
    logger.info(f"SENDER_EMAIL  Loaded: {bool(settings.SENDER_EMAIL)}")
    await connect_to_mongo()
    await create_indexes()
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    title="VV Residency Hotel Management API",
    description="Backend services for room booking, reservation dashboard, and staff management.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────
# Request logging (added first so it wraps all other middleware)
app.add_middleware(RequestLoggingMiddleware)

# CORS configuration to allow frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hotel-management-1vyunqqei-dabbarapoojitha30s-projects.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)
# Mount static files for Aadhaar uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ── Exception Handlers ─────────────────────────────────────────────
register_exception_handlers(app)

# ── Routes ──────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/", tags=["Health"])
def read_root():
    """Health check endpoint."""
    return {
        "message": "Welcome to VV Residency Hotel Management API!",
        "docs_url": "/docs",
        "status": "healthy",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Explicit health check endpoint for monitoring."""
    return {"status": "ok"}

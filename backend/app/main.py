"""
VV Residency Hotel Management API — Application entry point.
FastAPI application with lifespan management, middleware, and exception handlers.
"""
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.core.exceptions import register_exception_handlers
from app.database import (
    close_mongo_connection,
    connect_to_mongo,
    create_indexes,
)
from app.middleware.logging import RequestLoggingMiddleware
from app.routes import auth, bookings, dashboard, rooms

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent


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
    logger.info(f"GMAIL_APP_PASSWORD Loaded: {bool(settings.GMAIL_APP_PASSWORD)}")
    logger.info(f"SENDER_EMAIL        Loaded: {bool(settings.SENDER_EMAIL)}")
    await connect_to_mongo()
    await create_indexes()
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    title=f"{settings.HOTEL_NAME} Hotel Management API",
    description=f"Backend services for room booking, reservation dashboard, and staff management at {settings.HOTEL_NAME}.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────
# Request logging (added first so it wraps all other middleware)
app.add_middleware(RequestLoggingMiddleware)


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


# ── Configuration Helper & JavaScript Injection ─────────────────────
def get_hotel_config_js() -> str:
    """Safely serializes public hotel variables from .env to browser JavaScript."""
    words = [w for w in settings.HOTEL_NAME.strip().split() if w]
    if not words:
        initials = "HM"
    elif words[0].isupper() and len(words[0]) <= 3:
        initials = words[0]
    elif len(words) >= 2:
        initials = (words[0][0] + words[1][0]).upper()
    else:
        initials = words[0][:2].upper()

    config_dict = {
        "HOTEL_NAME": settings.HOTEL_NAME,
        "HOTEL_ADDRESS": settings.HOTEL_ADDRESS,
        "HOTEL_PHONE": settings.HOTEL_PHONE,
        "HOTEL_GSTIN": settings.HOTEL_GSTIN,
        "HOTEL_INITIALS": initials,
    }
    return f"window.HOTEL_CONFIG = Object.freeze({json.dumps(config_dict, indent=2)});"


def render_html_with_config(file_path: Path) -> HTMLResponse:
    """Reads HTML file and injects window.HOTEL_CONFIG before </head> for instant zero-latency loading."""
    if not file_path.is_file():
        return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)
    content = file_path.read_text(encoding="utf-8")
    script_tag = f"\n<script>\n{get_hotel_config_js()}\n</script>\n"
    if "</head>" in content:
        injected = content.replace("</head>", f"{script_tag}</head>", 1)
    else:
        injected = f"{script_tag}{content}"
    return HTMLResponse(content=injected)


# ── Health Endpoints ────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health_check():
    """Explicit health check endpoint for monitoring."""
    return {"status": "ok", "service": f"{settings.HOTEL_NAME} API & Web"}


# ── Dynamic Config Script for Browser ──────────────────────────────
@app.get("/config.js", tags=["Frontend"])
def serve_config_js():
    """Serves safe public hotel config from .env as a standalone script."""
    return Response(content=get_hotel_config_js(), media_type="application/javascript")


# ── Frontend HTML Routes (with safe .env injection) ────────────────
@app.get("/", tags=["Frontend"])
@app.get("/login", tags=["Frontend"])
@app.get("/login.html", tags=["Frontend"])
async def serve_login():
    """Serve the login page with injected hotel config."""
    return render_html_with_config(FRONTEND_DIR / "login.html")


@app.get("/booking", tags=["Frontend"])
@app.get("/index.html", tags=["Frontend"])
async def serve_booking():
    """Serve the booking dashboard with injected hotel config."""
    return render_html_with_config(FRONTEND_DIR / "index.html")


@app.get("/owner", tags=["Frontend"])
@app.get("/owner.html", tags=["Frontend"])
async def serve_owner():
    """Serve the owner dashboard with injected hotel config."""
    return render_html_with_config(FRONTEND_DIR / "owner.html")



# ── Mount Frontend Static Files ─────────────────────────────────────
# Serves all HTML files (login.html, index.html, owner.html, etc.),
# images, and other static assets directly.
# Mounted LAST so /api/* routes and /uploads take precedence.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


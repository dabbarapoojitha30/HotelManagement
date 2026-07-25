"""
Custom exception classes and FastAPI exception handlers.
Provides structured error responses across the entire API.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("VVResidencyAPI")


class VVResidencyException(Exception):
    """Base exception for all VV Residency business logic errors."""
    def __init__(self, detail: str, status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class NotFoundException(VVResidencyException):
    """Resource not found (404)."""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class BadRequestException(VVResidencyException):
    """Invalid request data (400)."""
    def __init__(self, detail: str = "Bad request"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class UnauthorizedException(VVResidencyException):
    """Authentication required or failed (401)."""
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(VVResidencyException):
    """Insufficient permissions (403)."""
    def __init__(self, detail: str = "Access denied"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


def register_exception_handlers(app: FastAPI):
    """
    Register custom exception handlers on the FastAPI app instance.
    Called once during app initialization in main.py.
    """

    @app.exception_handler(VVResidencyException)
    async def vvresidency_exception_handler(request: Request, exc: VVResidencyException):
        logger.warning(
            f"VVResidencyException: {exc.status_code} {exc.detail} "
            f"[{request.method} {request.url.path}]"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc} "
            f"[{request.method} {request.url.path}]",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

"""
Request/response logging middleware.
Logs method, path, status code, and response time for every request.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import logging

logger = logging.getLogger("VVResidencyAPI")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every incoming HTTP request and its response status.
    Useful for debugging, auditing, and performance monitoring.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"{method} {path}{'?' + query if query else ''} "
                f"→ 500 ERROR ({duration_ms:.1f}ms) — {type(exc).__name__}: {exc}"
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        status_code = response.status_code

        # Use appropriate log level based on status code
        if status_code >= 500:
            logger.error(
                f"{method} {path}{'?' + query if query else ''} "
                f"→ {status_code} ({duration_ms:.1f}ms)"
            )
        elif status_code >= 400:
            logger.warning(
                f"{method} {path}{'?' + query if query else ''} "
                f"→ {status_code} ({duration_ms:.1f}ms)"
            )
        else:
            logger.info(
                f"{method} {path}{'?' + query if query else ''} "
                f"→ {status_code} ({duration_ms:.1f}ms)"
            )

        return response

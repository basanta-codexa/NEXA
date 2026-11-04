"""Internal admin/debug console.

Serves a single-page test console for trusted local/staging environments.
The page itself is not a security boundary: every API call it makes still
requires a valid JWT and enforces RBAC. The route is disabled unless
ENABLE_ADMIN_CONSOLE is set to a truthy value, and should stay disabled in
production.
"""

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["Admin Console"])

CONSOLE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "static",
    "console",
    "test-console.html",
)
_TRUTHY = {"1", "true", "yes", "on"}


def console_enabled() -> bool:
    return os.getenv("ENABLE_ADMIN_CONSOLE", "").strip().lower() in _TRUTHY


@router.get("/console", include_in_schema=False)
def admin_console():
    if not console_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(CONSOLE_FILE, media_type="text/html")

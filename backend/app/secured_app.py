import json

from fastapi import Request, Response

from app.auth_app import (
    COOKIE_NAME,
    _load_active_user,
    app,
    parse_session_token,
)


def required_roles(path: str, method: str):
    method = method.upper()

    if path.startswith("/api/admin/users"):
        return {"ADMIN"}

    if method == "DELETE" and path.startswith("/api/orders/"):
        return {"ADMIN"}

    if method == "POST" and path.rstrip("/") == "/api/customers":
        return {"ADMIN", "KASIR"}

    if path.startswith("/api/orders"):
        if method == "POST" and path.rstrip("/") == "/api/orders":
            return {"ADMIN", "KASIR"}
        if "/payments" in path or path.endswith("/mark-paid"):
            return {"ADMIN", "KASIR"}
        if path.endswith("/edit-v2"):
            return {"ADMIN", "KASIR"}
        if path.endswith("/status-v2") or path.endswith("/status"):
            return {"ADMIN", "KASIR", "STAFF"}

    return None


@app.middleware("http")
async def strict_role_middleware(request: Request, call_next):
    allowed = required_roles(request.url.path, request.method)
    if not allowed:
        return await call_next(request)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return Response(
            content=json.dumps({"detail": "Silakan login"}),
            status_code=401,
            media_type="application/json",
        )

    try:
        payload = parse_session_token(token)
        user = _load_active_user(int(payload["uid"]))
    except Exception:
        return Response(
            content=json.dumps({"detail": "Sesi login tidak valid"}),
            status_code=401,
            media_type="application/json",
        )

    if user["role"] not in allowed:
        return Response(
            content=json.dumps({"detail": "Role user tidak memiliki izin untuk aksi ini"}),
            status_code=403,
            media_type="application/json",
        )

    return await call_next(request)

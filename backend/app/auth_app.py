import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from app.main import get_db_connection
from app.operations import app


AUTH_SECRET = os.getenv("AUTH_SECRET", "").strip()
COOKIE_NAME = "dayu_session"
SESSION_TTL = int(os.getenv("AUTH_SESSION_TTL_SECONDS", "43200"))
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
PASSWORD_ITERATIONS = 260000
VALID_ROLES = {"ADMIN", "KASIR", "STAFF"}


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    name: str
    username: str
    password: str
    role: str = "STAFF"


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password minimal 8 karakter")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_encoded, hash_encoded = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _b64decode(salt_encoded)
        expected = _b64decode(hash_encoded)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _secret() -> bytes:
    if not AUTH_SECRET or len(AUTH_SECRET) < 32:
        raise RuntimeError("AUTH_SECRET wajib diset minimal 32 karakter")
    return AUTH_SECRET.encode()


def create_session_token(user_id: int) -> str:
    payload = {
        "uid": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_TTL,
        "nonce": secrets.token_hex(8),
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def parse_session_token(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(_b64decode(encoded))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Sesi login tidak valid atau sudah berakhir")


def _load_active_user(user_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, username, role, is_active
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    if not row or not row[4]:
        raise HTTPException(status_code=401, detail="User tidak aktif")
    return {
        "id": row[0],
        "name": row[1],
        "username": row[2],
        "role": row[3].upper(),
        "is_active": row[4],
    }


def current_user_from_request(request: Request):
    user = getattr(request.state, "current_user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login")
    return user


def require_admin(request: Request):
    user = current_user_from_request(request)
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Hanya ADMIN yang memiliki akses")
    return user


def _is_public_path(path: str) -> bool:
    return path in {
        "/",
        "/health",
        "/health/database",
        "/api/auth/login",
    }


def _required_roles(path: str, method: str):
    method = method.upper()
    if path.startswith("/api/admin/users"):
        return {"ADMIN"}
    if method == "DELETE" and "/api/orders/" in path:
        return {"ADMIN"}
    if method in {"POST", "PATCH", "DELETE"} and path.startswith("/api/orders"):
        return {"ADMIN", "KASIR", "STAFF"}
    return None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if _is_public_path(path):
        return await call_next(request)

    if path.startswith("/api/"):
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
            request.state.current_user = user
        except HTTPException as error:
            return Response(
                content=json.dumps({"detail": error.detail}),
                status_code=error.status_code,
                media_type="application/json",
            )
        except Exception:
            return Response(
                content=json.dumps({"detail": "Sesi login tidak valid"}),
                status_code=401,
                media_type="application/json",
            )

        allowed = _required_roles(path, request.method)
        if allowed and user["role"] not in allowed:
            return Response(
                content=json.dumps({"detail": "Role user tidak memiliki izin"}),
                status_code=403,
                media_type="application/json",
            )

        # Force all legacy actor fields to the authenticated user.
        if request.method.upper() in {"POST", "PATCH", "DELETE"}:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    raw = await request.body()
                    data = json.loads(raw or b"{}")
                    if isinstance(data, dict):
                        user_id = user["id"]
                        for key in ("created_by", "changed_by", "updated_by", "actor_user_id"):
                            if key in data or path.startswith("/api/orders"):
                                data[key] = user_id
                        replacement = json.dumps(data).encode()

                        async def receive():
                            return {"type": "http.request", "body": replacement, "more_body": False}

                        request._receive = receive
                except Exception:
                    pass

    return await call_next(request)


@app.post("/api/auth/login")
def login(request: LoginRequest, response: Response):
    username = request.username.strip().lower()
    if not username or not request.password:
        raise HTTPException(status_code=400, detail="Username dan password wajib diisi")

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, username, password_hash, role, is_active
                FROM users
                WHERE LOWER(username) = %s
                """,
                (username,),
            )
            row = cursor.fetchone()

    if not row or not row[5] or not verify_password(request.password, row[3]):
        raise HTTPException(status_code=401, detail="Username atau password salah")

    token = create_session_token(row[0])
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL,
        path="/",
    )
    return {
        "status": "success",
        "user": {"id": row[0], "name": row[1], "username": row[2], "role": row[4].upper()},
    }


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "success"}


@app.get("/api/auth/me")
def auth_me(request: Request):
    return current_user_from_request(request)


@app.get("/api/admin/users")
def admin_list_users(request: Request):
    require_admin(request)
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, username, role, is_active, created_at, updated_at
                FROM users
                ORDER BY id
                """
            )
            rows = cursor.fetchall()
    return [
        {
            "id": row[0],
            "name": row[1],
            "username": row[2],
            "role": row[3].upper(),
            "is_active": row[4],
            "created_at": row[5].isoformat(),
            "updated_at": row[6].isoformat(),
        }
        for row in rows
    ]


@app.post("/api/admin/users", status_code=201)
def admin_create_user(request: Request, payload: CreateUserRequest):
    require_admin(request)
    name = payload.name.strip()
    username = payload.username.strip().lower()
    role = payload.role.upper().strip()
    if not name or not username:
        raise HTTPException(status_code=400, detail="Nama dan username wajib diisi")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Role harus ADMIN, KASIR, atau STAFF")
    password_hash = hash_password(payload.password)
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (name, username, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, TRUE)
                    RETURNING id, name, username, role, is_active
                    """,
                    (name, username, password_hash, role),
                )
                row = cursor.fetchone()
            connection.commit()
    except Exception as error:
        if "users_username_key" in str(error) or "duplicate" in str(error).lower():
            raise HTTPException(status_code=409, detail="Username sudah digunakan")
        raise HTTPException(status_code=500, detail=str(error))
    return {"id": row[0], "name": row[1], "username": row[2], "role": row[3], "is_active": row[4]}


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, request: Request, payload: UpdateUserRequest):
    actor = require_admin(request)
    role = payload.role.upper().strip() if payload.role else None
    if role and role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Role harus ADMIN, KASIR, atau STAFF")
    if user_id == actor["id"] and payload.is_active is False:
        raise HTTPException(status_code=409, detail="User yang sedang login tidak boleh menonaktifkan dirinya sendiri")

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name, username, role, is_active FROM users WHERE id = %s", (user_id,))
            existing = cursor.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="User tidak ditemukan")

            name = payload.name.strip() if payload.name is not None else existing[1]
            new_role = role or existing[3].upper()
            is_active = payload.is_active if payload.is_active is not None else existing[4]
            password_hash = hash_password(payload.password) if payload.password else None

            if existing[3].upper() == "ADMIN" and (new_role != "ADMIN" or not is_active):
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND is_active = TRUE")
                if cursor.fetchone()[0] <= 1:
                    raise HTTPException(status_code=409, detail="Minimal harus ada satu ADMIN aktif")

            cursor.execute(
                """
                UPDATE users
                SET name = %s,
                    role = %s,
                    is_active = %s,
                    password_hash = COALESCE(%s, password_hash),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, name, username, role, is_active
                """,
                (name, new_role, is_active, password_hash, user_id),
            )
            row = cursor.fetchone()
        connection.commit()

    return {"id": row[0], "name": row[1], "username": row[2], "role": row[3], "is_active": row[4]}


def bootstrap_admin_password():
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    if not password:
        return
    username = os.getenv("ADMIN_BOOTSTRAP_USERNAME", "admin").strip().lower()
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, password_hash FROM users WHERE LOWER(username) = %s", (username,))
            row = cursor.fetchone()
            if row and not str(row[1]).startswith("pbkdf2_sha256$"):
                cursor.execute(
                    "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
                    (hash_password(password), row[0]),
                )
                connection.commit()


@app.on_event("startup")
def startup_bootstrap_auth():
    if AUTH_SECRET and len(AUTH_SECRET) >= 32:
        bootstrap_admin_password()

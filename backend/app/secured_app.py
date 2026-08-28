import json

from fastapi import Request, Response

from app.auth_app import (
    COOKIE_NAME,
    _load_active_user,
    app,
    parse_session_token,
)
from app.main import get_db_connection


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


@app.get("/api/orders-list-v2")
def get_orders_list_v2():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    o.id,
                    o.order_number,
                    c.name AS customer,
                    c.phone,
                    o.hotel_name,
                    o.room_number,
                    o.service_speed,
                    o.status,
                    o.total_weight,
                    o.subtotal,
                    o.discount,
                    o.total,
                    o.payment_status,
                    o.requested_finish_at,
                    o.created_at,
                    u.name AS received_by
                FROM orders o
                JOIN customers c ON c.id = o.customer_id
                LEFT JOIN users u ON u.id = o.created_by
                ORDER BY o.id DESC
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "order_number": row[1],
            "customer": row[2],
            "phone": row[3],
            "hotel_name": row[4],
            "room_number": row[5],
            "service_speed": row[6],
            "status": row[7],
            "total_weight": float(row[8]) if row[8] is not None else 0,
            "subtotal": float(row[9]),
            "discount": float(row[10]),
            "total": float(row[11]),
            "payment_status": row[12],
            "requested_finish_at": row[13].isoformat() if row[13] else None,
            "created_at": row[14].isoformat(),
            "received_by": row[15],
        }
        for row in rows
    ]

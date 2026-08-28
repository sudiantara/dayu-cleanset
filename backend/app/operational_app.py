import json

from fastapi import Request, Response

from app.secured_app_v2 import app
from app.main import get_db_connection
from app.auth_app import COOKIE_NAME, _load_active_user, parse_session_token


@app.middleware("http")
async def operational_auth_middleware(request: Request, call_next):
    if not request.url.path.startswith("/api/operational-control"):
        return await call_next(request)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return Response(
            content=json.dumps({"detail": "Silakan login"}),
            status_code=401,
            media_type="application/json",
        )
    try:
        user = _load_active_user(int(parse_session_token(token)["uid"]))
    except Exception:
        return Response(
            content=json.dumps({"detail": "Sesi login tidak valid"}),
            status_code=401,
            media_type="application/json",
        )
    request.state.operational_user = user
    return await call_next(request)


@app.get("/api/operational-control-v1")
def operational_control_v1():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    o.order_number,
                    c.name,
                    c.phone,
                    o.hotel_name,
                    o.room_number,
                    o.service_speed,
                    o.status,
                    o.payment_status,
                    o.total_weight,
                    o.total,
                    o.requested_finish_at,
                    o.created_at,
                    o.updated_at,
                    CASE
                        WHEN o.requested_finish_at IS NULL THEN 'NO_TARGET'
                        WHEN o.requested_finish_at < NOW() THEN 'OVERDUE'
                        WHEN o.requested_finish_at <= NOW() + INTERVAL '3 hours' THEN 'DUE_SOON'
                        ELSE 'ON_TRACK'
                    END AS deadline_state,
                    CASE
                        WHEN o.requested_finish_at IS NULL THEN NULL
                        ELSE EXTRACT(EPOCH FROM (o.requested_finish_at - NOW())) / 60
                    END AS minutes_to_target
                FROM orders o
                JOIN customers c ON c.id = o.customer_id
                WHERE o.status NOT IN ('COMPLETE', 'PICKED_UP', 'CANCELLED')
                ORDER BY
                    CASE WHEN o.requested_finish_at IS NULL THEN 1 ELSE 0 END,
                    o.requested_finish_at ASC NULLS LAST,
                    o.id ASC
                """
            )
            rows = cursor.fetchall()

    orders = []
    for row in rows:
        orders.append({
            "order_number": row[0],
            "customer": row[1],
            "phone": row[2],
            "hotel_name": row[3],
            "room_number": row[4],
            "service_speed": row[5],
            "status": row[6],
            "payment_status": row[7],
            "total_weight": float(row[8] or 0),
            "total": float(row[9] or 0),
            "requested_finish_at": row[10].isoformat() if row[10] else None,
            "created_at": row[11].isoformat(),
            "updated_at": row[12].isoformat(),
            "deadline_state": row[13],
            "minutes_to_target": float(row[14]) if row[14] is not None else None,
        })

    return {
        "summary": {
            "active": len(orders),
            "overdue": sum(1 for o in orders if o["deadline_state"] == "OVERDUE"),
            "due_soon": sum(1 for o in orders if o["deadline_state"] == "DUE_SOON"),
            "ready": sum(1 for o in orders if o["status"] == "READY"),
            "unpaid": sum(1 for o in orders if o["payment_status"] != "PAID"),
            "express": sum(1 for o in orders if o["service_speed"] == "EXPRESS"),
        },
        "orders": orders,
    }

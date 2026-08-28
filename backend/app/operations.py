from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from app.main import get_db_connection, send_n8n_event
from app.order_overview import app


VALID_STATUSES = ["NEW", "RECEIVED", "WASHING", "READY", "PICKED_UP", "DELIVERING", "COMPLETE"]
LEGACY_FORWARD = {"DRYING": ["READY"], "IRONING": ["READY"]}
STATUS_FLOW = {
    "NEW": ["RECEIVED"],
    "RECEIVED": ["WASHING"],
    "WASHING": ["READY"],
    "READY": ["PICKED_UP", "DELIVERING"],
    "PICKED_UP": ["COMPLETE"],
    "DELIVERING": ["COMPLETE"],
    "COMPLETE": [],
}
HANDOFF_STATUSES = {"PICKED_UP", "DELIVERING", "COMPLETE"}


class EditOrderRequest(BaseModel):
    hotel_name: str
    room_number: Optional[str] = None
    location_notes: Optional[str] = None
    service_speed: str
    requested_finish_at: Optional[str] = None
    total_weight: float
    instagram_followed: bool = False
    google_reviewed: bool = False
    special_discount: float = 0
    special_discount_reason: Optional[str] = None
    notes: Optional[str] = None
    updated_by: int = 1


class StatusV2Request(BaseModel):
    status: str
    note: Optional[str] = None
    changed_by: int = 1


class DeleteOrderRequest(BaseModel):
    actor_user_id: int = 1
    reason: Optional[str] = None


def _get_active_user(cursor, user_id: int):
    cursor.execute("SELECT id, name, role FROM users WHERE id=%s AND is_active=TRUE", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User/operator tidak ditemukan atau nonaktif")
    return user


def _allowed_next_statuses(current_status: str):
    current = (current_status or "").upper().strip()
    return LEGACY_FORWARD.get(current, STATUS_FLOW.get(current, []))


@app.get("/api/users/active")
def get_active_users():
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, name, username, role FROM users WHERE is_active=TRUE ORDER BY name")
                rows = cursor.fetchall()
        return [{"id": r[0], "name": r[1], "username": r[2], "role": r[3]} for r in rows]
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.patch("/api/orders/{order_number}/edit-v2")
def edit_order_v2(order_number: str, request: EditOrderRequest):
    speed = request.service_speed.upper().strip()
    if speed not in ["NORMAL", "EXPRESS"]:
        raise HTTPException(status_code=400, detail="Service harus NORMAL atau EXPRESS")
    if request.total_weight <= 0:
        raise HTTPException(status_code=400, detail="Berat harus lebih dari 0 KG")
    if not request.hotel_name.strip():
        raise HTTPException(status_code=400, detail="Hotel / Villa wajib diisi")
    if request.special_discount < 0:
        raise HTTPException(status_code=400, detail="Diskon nego tidak boleh negatif")

    price_per_kg = 30000 if speed == "NORMAL" else 55000
    subtotal = request.total_weight * price_per_kg
    promo_discount = subtotal * 0.05 if request.instagram_followed and request.google_reviewed else 0
    discount = promo_discount + request.special_discount
    if discount > subtotal:
        raise HTTPException(status_code=400, detail="Total diskon tidak boleh melebihi subtotal")
    if request.special_discount > 0 and not (request.special_discount_reason or "").strip():
        raise HTTPException(status_code=400, detail="Alasan diskon nego wajib diisi")
    total = subtotal - discount

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                user = _get_active_user(cursor, request.updated_by)
                cursor.execute("SELECT id, status FROM orders WHERE order_number=%s", (order_number,))
                order = cursor.fetchone()
                if not order:
                    raise HTTPException(status_code=404, detail="Order tidak ditemukan")
                if order[1] == "COMPLETE":
                    raise HTTPException(status_code=409, detail="Order COMPLETE sudah final dan tidak dapat diedit")
                cursor.execute(
                    """UPDATE orders SET hotel_name=%s,room_number=%s,location_notes=%s,service_speed=%s,
                    requested_finish_at=%s,total_weight=%s,instagram_followed=%s,google_reviewed=%s,
                    promo_discount=%s,special_discount=%s,special_discount_reason=%s,subtotal=%s,discount=%s,
                    total=%s,notes=%s,updated_at=NOW() WHERE order_number=%s""",
                    (request.hotel_name.strip(), (request.room_number or "").strip() or None,
                     (request.location_notes or "").strip() or None, speed, request.requested_finish_at,
                     request.total_weight, request.instagram_followed, request.google_reviewed,
                     promo_discount, request.special_discount, (request.special_discount_reason or "").strip() or None,
                     subtotal, discount, total, (request.notes or "").strip() or None, order_number),
                )
                cursor.execute(
                    "INSERT INTO order_status_history(order_id,status,note,changed_by) SELECT id,status,%s,%s FROM orders WHERE order_number=%s",
                    (f"Data order diedit oleh {user[1]}", request.updated_by, order_number),
                )
            connection.commit()
        return {"status":"success","message":"Order berhasil diperbarui","order_number":order_number,
                "subtotal":subtotal,"discount":discount,"total":total,"updated_by":user[1]}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.patch("/api/orders/{order_number}/status-v2")
def update_order_status_v2(order_number: str, request: StatusV2Request):
    new_status = request.status.upper().strip()
    if new_status not in VALID_STATUSES and new_status not in {"READY"}:
        raise HTTPException(status_code=400, detail="Status tidak valid pada alur laundry saat ini")

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                user = _get_active_user(cursor, request.changed_by)
                cursor.execute(
                    """SELECT o.id,o.status,o.payment_status,c.name,o.hotel_name,o.room_number,o.service_speed,o.total
                    FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.order_number=%s""",
                    (order_number,),
                )
                order = cursor.fetchone()
                if not order:
                    raise HTTPException(status_code=404, detail="Order tidak ditemukan")

                current_status = (order[1] or "").upper()
                allowed = _allowed_next_statuses(current_status)
                if current_status == "COMPLETE":
                    raise HTTPException(status_code=409, detail="Order sudah COMPLETE dan status bersifat final")
                if new_status not in allowed:
                    allowed_text = ", ".join(allowed) if allowed else "tidak ada"
                    raise HTTPException(
                        status_code=409,
                        detail=f"Status tidak boleh mundur atau lompat. Dari {current_status} hanya boleh ke: {allowed_text}",
                    )
                if new_status in HANDOFF_STATUSES and order[2] != "PAID":
                    raise HTTPException(
                        status_code=409,
                        detail=f"Order belum lunas. Lunasi pembayaran sebelum masuk status {new_status}",
                    )

                cursor.execute(
                    """UPDATE orders SET status=%s,updated_at=NOW(),
                    completed_at=CASE WHEN %s='COMPLETE' THEN NOW() ELSE completed_at END WHERE id=%s""",
                    (new_status, new_status, order[0]),
                )
                note = (request.note or "").strip() or None
                cursor.execute(
                    "INSERT INTO order_status_history(order_id,status,note,changed_by) VALUES(%s,%s,%s,%s)",
                    (order[0], new_status, note, request.changed_by),
                )
            connection.commit()

        handoff_type = "PICKUP" if new_status == "PICKED_UP" else "DELIVERY" if new_status == "DELIVERING" else None
        send_n8n_event(
            event="STATUS_CHANGED",
            message=f"Status {order_number}: {current_status} → {new_status}",
            data={
                "order_number": order_number,
                "customer": order[3],
                "hotel_name": order[4],
                "room_number": order[5],
                "service_speed": order[6],
                "total": float(order[7] or 0),
                "old_status": current_status,
                "status": new_status,
                "handoff_type": handoff_type,
                "note": request.note,
                "operator_id": request.changed_by,
                "operator_name": user[1],
                "is_final": new_status == "COMPLETE",
            },
        )
        return {"status":"success","message":"Status berhasil diperbarui","order_number":order_number,
                "old_status":current_status,"new_status":new_status,"operator":user[1],"allowed_next":_allowed_next_statuses(new_status)}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.delete("/api/orders/{order_number}/delete-v2")
def delete_order_v2(order_number: str, request: DeleteOrderRequest):
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                user = _get_active_user(cursor, request.actor_user_id)
                if user[2].upper() != "ADMIN":
                    raise HTTPException(status_code=403, detail="Hanya ADMIN yang boleh menghapus order")
                cursor.execute(
                    """SELECT o.id,o.status,COALESCE(SUM(p.amount),0) FROM orders o LEFT JOIN payments p ON p.order_id=o.id
                    WHERE o.order_number=%s GROUP BY o.id,o.status""", (order_number,))
                order = cursor.fetchone()
                if not order:
                    raise HTTPException(status_code=404, detail="Order tidak ditemukan")
                if order[1] == "COMPLETE":
                    raise HTTPException(status_code=409, detail="Order COMPLETE tidak boleh dihapus")
                if float(order[2]) > 0:
                    raise HTTPException(status_code=409, detail="Order yang sudah memiliki pembayaran tidak boleh dihapus")
                cursor.execute("DELETE FROM orders WHERE id=%s", (order[0],))
            connection.commit()
        return {"status":"success","message":"Order berhasil dihapus","order_number":order_number,
                "deleted_by":user[1],"reason":request.reason}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

import json
import re
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from app.secured_app_v2 import app
from app.main import get_db_connection, send_n8n_event
from app.auth_app import COOKIE_NAME, _load_active_user, parse_session_token


class CommunicationLogRequest(BaseModel):
    event_type: str
    message: str
    channel: str = "WHATSAPP"
    status: str = "OPENED"


def _current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Silakan login")
    try:
        return _load_active_user(int(parse_session_token(token)["uid"]))
    except Exception:
        raise HTTPException(status_code=401, detail="Sesi login tidak valid")


def _wa_number(phone: str):
    raw = (phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return digits
    if digits.startswith("0"):
        return "62" + digits[1:]
    return digits


def _rupiah(value):
    return f"Rp {float(value or 0):,.0f}".replace(",", ".")


@app.middleware("http")
async def operational_auth_middleware(request: Request, call_next):
    path = request.url.path
    if request.method.upper() == "PATCH" and path.startswith("/api/orders/") and path.endswith("/status") and not path.endswith("/status-v2"):
        return Response(content=json.dumps({"detail":"Endpoint status lama dinonaktifkan. Gunakan alur status-v2 yang forward-only."}), status_code=410, media_type="application/json")
    if not path.startswith("/api/operational-control"):
        return await call_next(request)
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return Response(content=json.dumps({"detail":"Silakan login"}), status_code=401, media_type="application/json")
    try:
        user = _load_active_user(int(parse_session_token(token)["uid"]))
    except Exception:
        return Response(content=json.dumps({"detail":"Sesi login tidak valid"}), status_code=401, media_type="application/json")
    request.state.operational_user = user
    return await call_next(request)


@app.get("/api/operational-control-v1")
def operational_control_v1():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT o.order_number,c.name,c.phone,o.hotel_name,o.room_number,o.service_speed,o.status,
                       o.payment_status,o.total_weight,o.total,o.requested_finish_at,o.created_at,o.updated_at,
                       CASE
                         WHEN o.requested_finish_at IS NULL THEN 'NO_TARGET'
                         WHEN o.requested_finish_at < NOW() THEN 'OVERDUE'
                         WHEN o.requested_finish_at <= NOW()+INTERVAL '3 hours' THEN 'DUE_SOON'
                         ELSE 'ON_TRACK'
                       END deadline_state,
                       CASE WHEN o.requested_finish_at IS NULL THEN NULL
                            ELSE EXTRACT(EPOCH FROM(o.requested_finish_at-NOW()))/60 END minutes_to_target,
                       rs.ready_since,
                       CASE WHEN rs.ready_since IS NULL THEN NULL ELSE EXTRACT(EPOCH FROM(NOW()-rs.ready_since))/60 END ready_age_minutes,
                       cc.last_contact_at
                FROM orders o
                JOIN customers c ON c.id=o.customer_id
                LEFT JOIN LATERAL (
                    SELECT h.changed_at ready_since
                    FROM order_status_history h
                    WHERE h.order_id=o.id AND h.status='READY'
                    ORDER BY h.changed_at DESC LIMIT 1
                ) rs ON TRUE
                LEFT JOIN LATERAL (
                    SELECT MAX(ccom.created_at) last_contact_at
                    FROM customer_communications ccom
                    WHERE ccom.order_id=o.id
                ) cc ON TRUE
                WHERE o.status NOT IN ('COMPLETE','CANCELLED')
                ORDER BY
                  CASE
                    WHEN o.requested_finish_at < NOW() THEN 0
                    WHEN o.status='READY' AND COALESCE(EXTRACT(EPOCH FROM(NOW()-rs.ready_since))/60,0)>=120 THEN 1
                    WHEN o.requested_finish_at <= NOW()+INTERVAL '3 hours' THEN 2
                    WHEN o.service_speed='EXPRESS' THEN 3
                    WHEN o.payment_status<>'PAID' AND o.status='READY' THEN 4
                    ELSE 5
                  END,
                  o.requested_finish_at ASC NULLS LAST,o.id ASC
                """
            )
            rows = cursor.fetchall()

    orders = []
    for row in rows:
        ready_age = float(row[16]) if row[16] is not None else None
        escalation = []
        if row[13] == "OVERDUE": escalation.append("OVERDUE")
        if row[13] == "DUE_SOON": escalation.append("DUE_SOON")
        if row[6] == "READY" and ready_age is not None and ready_age >= 120: escalation.append("READY_AGING")
        if row[6] == "READY" and row[7] != "PAID": escalation.append("READY_UNPAID")
        if row[13] == "NO_TARGET": escalation.append("NO_TARGET")
        if row[5] == "EXPRESS": escalation.append("EXPRESS")
        needs_contact = row[6] == "READY" and (row[17] is None or (datetime.now(row[17].tzinfo) - row[17]).total_seconds() >= 7200)
        orders.append({
            "order_number":row[0],"customer":row[1],"phone":row[2],"hotel_name":row[3],"room_number":row[4],
            "service_speed":row[5],"status":row[6],"payment_status":row[7],"total_weight":float(row[8] or 0),"total":float(row[9] or 0),
            "requested_finish_at":row[10].isoformat() if row[10] else None,"created_at":row[11].isoformat(),"updated_at":row[12].isoformat(),
            "deadline_state":row[13],"minutes_to_target":float(row[14]) if row[14] is not None else None,
            "ready_since":row[15].isoformat() if row[15] else None,"ready_age_minutes":ready_age,
            "last_contact_at":row[17].isoformat() if row[17] else None,"needs_customer_contact":needs_contact,
            "escalations":escalation,"needs_attention":bool(escalation)
        })

    ready = [o for o in orders if o["status"] == "READY"]
    exceptions = [o for o in orders if o["needs_attention"]]
    handover = {
        "generated_at":datetime.now().isoformat(),"active":len(orders),"washing":sum(1 for o in orders if o["status"]=="WASHING"),
        "ready":len(ready),"picked_up":sum(1 for o in orders if o["status"]=="PICKED_UP"),"delivery":sum(1 for o in orders if o["status"]=="DELIVERING"),
        "overdue":sum(1 for o in orders if o["deadline_state"]=="OVERDUE"),"due_soon":sum(1 for o in orders if o["deadline_state"]=="DUE_SOON"),
        "ready_over_2h":sum(1 for o in ready if (o["ready_age_minutes"] or 0)>=120),"ready_unpaid":sum(1 for o in ready if o["payment_status"]!="PAID"),
        "express":sum(1 for o in orders if o["service_speed"]=="EXPRESS"),"exceptions":len(exceptions),
        "customer_contact_due":sum(1 for o in orders if o["needs_customer_contact"])
    }
    return {
        "summary":{"active":len(orders),"overdue":handover["overdue"],"due_soon":handover["due_soon"],"ready":handover["ready"],
                   "unpaid":sum(1 for o in orders if o["payment_status"]!="PAID"),"express":handover["express"],
                   "ready_over_2h":handover["ready_over_2h"],"exceptions":handover["exceptions"],"customer_contact_due":handover["customer_contact_due"]},
        "handover":handover,"exceptions":exceptions[:10],"orders":orders
    }


@app.get("/api/orders/{order_number}/communication-v1")
def order_communication_v1(order_number: str, request: Request):
    _current_user(request)
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT o.id,o.order_number,c.name,c.phone,o.hotel_name,o.room_number,o.status,o.payment_status,
                       o.total,o.requested_finish_at,o.service_speed,
                       (SELECT MAX(changed_at) FROM order_status_history WHERE order_id=o.id AND status='READY') ready_since
                FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.order_number=%s
            """, (order_number,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Order tidak ditemukan")
            cursor.execute("""
                SELECT cc.id,cc.channel,cc.event_type,cc.recipient,cc.message,cc.status,cc.created_at,u.name
                FROM customer_communications cc LEFT JOIN users u ON u.id=cc.created_by
                WHERE cc.order_id=%s ORDER BY cc.created_at DESC LIMIT 30
            """, (row[0],))
            history = cursor.fetchall()

    name, total = row[2], _rupiah(row[8])
    location = row[4] or "lokasi Anda"
    if row[5]: location += f" kamar {row[5]}"
    payment_text = "sudah lunas" if row[7] == "PAID" else f"belum lunas, total {total}"
    templates = {
        "ORDER_RECEIVED": f"Halo {name}, laundry Anda dengan nomor {row[1]} sudah kami terima. Kami akan mengabari kembali saat laundry siap. Terima kasih - Dayu Cleanest Laundry.",
        "READY": f"Halo {name}, laundry Anda {row[1]} sudah READY dan siap diserahkan. Status pembayaran: {payment_text}. Lokasi: {location}. Terima kasih - Dayu Cleanest Laundry.",
        "PAYMENT_REMINDER": f"Halo {name}, laundry Anda {row[1]} sudah siap. Mohon menyelesaikan pembayaran sebesar {total} sebelum pickup/delivery. Terima kasih - Dayu Cleanest Laundry.",
        "PICKUP_REMINDER": f"Halo {name}, pengingat bahwa laundry Anda {row[1]} sudah siap untuk diambil. Silakan kabari kami jika membutuhkan bantuan delivery. Terima kasih - Dayu Cleanest Laundry.",
        "DELIVERY": f"Halo {name}, laundry Anda {row[1]} sedang dalam proses DELIVERY menuju {location}. Mohon standby untuk menerima laundry. Terima kasih - Dayu Cleanest Laundry.",
        "THANK_YOU": f"Halo {name}, order laundry {row[1]} sudah COMPLETE. Terima kasih sudah menggunakan Dayu Cleanest Laundry. Kami tunggu order berikutnya 😊"
    }
    return {
        "order_number":row[1],"customer":name,"phone":row[3],"whatsapp_number":_wa_number(row[3]),"status":row[6],"payment_status":row[7],
        "total":float(row[8] or 0),"ready_since":row[11].isoformat() if row[11] else None,"templates":templates,
        "history":[{"id":h[0],"channel":h[1],"event_type":h[2],"recipient":h[3],"message":h[4],"status":h[5],"created_at":h[6].isoformat(),"operator":h[7]} for h in history]
    }


@app.post("/api/orders/{order_number}/communication-v1")
def log_order_communication_v1(order_number: str, payload: CommunicationLogRequest, request: Request):
    user = _current_user(request)
    event_type = payload.event_type.upper().strip()
    channel = payload.channel.upper().strip()
    status = payload.status.upper().strip()
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong")
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT o.id,c.name,c.phone FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.order_number=%s", (order_number,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Order tidak ditemukan")
            cursor.execute("""
                INSERT INTO customer_communications(order_id,channel,event_type,recipient,message,status,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id,created_at
            """, (order[0], channel, event_type, order[2], payload.message.strip(), status, user["id"]))
            saved = cursor.fetchone()
        connection.commit()
    send_n8n_event(event="CUSTOMER_COMMUNICATION", message=f"{event_type} {order_number} untuk {order[1]}", data={
        "order_number":order_number,"customer_name":order[1],"customer_phone":order[2],"channel":channel,"event_type":event_type,
        "communication_status":status,"message":payload.message.strip(),"operator_id":user["id"],"operator_name":user["name"]
    })
    return {"status":"success","id":saved[0],"created_at":saved[1].isoformat(),"operator":user["name"]}

import json
from datetime import datetime

from fastapi import Request, Response

from app.secured_app_v2 import app
from app.main import get_db_connection
from app.auth_app import COOKIE_NAME, _load_active_user, parse_session_token


@app.middleware("http")
async def operational_auth_middleware(request: Request, call_next):
    path=request.url.path
    if request.method.upper()=="PATCH" and path.startswith("/api/orders/") and path.endswith("/status") and not path.endswith("/status-v2"):
        return Response(content=json.dumps({"detail":"Endpoint status lama dinonaktifkan. Gunakan alur status-v2 yang forward-only."}),status_code=410,media_type="application/json")
    if not path.startswith("/api/operational-control"):
        return await call_next(request)
    token=request.cookies.get(COOKIE_NAME)
    if not token:
        return Response(content=json.dumps({"detail":"Silakan login"}),status_code=401,media_type="application/json")
    try:user=_load_active_user(int(parse_session_token(token)["uid"]))
    except Exception:return Response(content=json.dumps({"detail":"Sesi login tidak valid"}),status_code=401,media_type="application/json")
    request.state.operational_user=user
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
                       CASE WHEN rs.ready_since IS NULL THEN NULL ELSE EXTRACT(EPOCH FROM(NOW()-rs.ready_since))/60 END ready_age_minutes
                FROM orders o
                JOIN customers c ON c.id=o.customer_id
                LEFT JOIN LATERAL (
                    SELECT h.changed_at ready_since
                    FROM order_status_history h
                    WHERE h.order_id=o.id AND h.status='READY'
                    ORDER BY h.changed_at DESC LIMIT 1
                ) rs ON TRUE
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
            rows=cursor.fetchall()

    orders=[]
    for row in rows:
        ready_age=float(row[16]) if row[16] is not None else None
        escalation=[]
        if row[13]=="OVERDUE":escalation.append("OVERDUE")
        if row[13]=="DUE_SOON":escalation.append("DUE_SOON")
        if row[6]=="READY" and ready_age is not None and ready_age>=120:escalation.append("READY_AGING")
        if row[6]=="READY" and row[7]!="PAID":escalation.append("READY_UNPAID")
        if row[13]=="NO_TARGET":escalation.append("NO_TARGET")
        if row[5]=="EXPRESS":escalation.append("EXPRESS")
        orders.append({"order_number":row[0],"customer":row[1],"phone":row[2],"hotel_name":row[3],"room_number":row[4],"service_speed":row[5],"status":row[6],"payment_status":row[7],"total_weight":float(row[8] or 0),"total":float(row[9] or 0),"requested_finish_at":row[10].isoformat() if row[10] else None,"created_at":row[11].isoformat(),"updated_at":row[12].isoformat(),"deadline_state":row[13],"minutes_to_target":float(row[14]) if row[14] is not None else None,"ready_since":row[15].isoformat() if row[15] else None,"ready_age_minutes":ready_age,"escalations":escalation,"needs_attention":bool(escalation)})

    ready=[o for o in orders if o["status"]=="READY"]
    exceptions=[o for o in orders if o["needs_attention"]]
    handover={"generated_at":datetime.now().isoformat(),"active":len(orders),"washing":sum(1 for o in orders if o["status"]=="WASHING"),"ready":len(ready),"picked_up":sum(1 for o in orders if o["status"]=="PICKED_UP"),"delivery":sum(1 for o in orders if o["status"]=="DELIVERING"),"overdue":sum(1 for o in orders if o["deadline_state"]=="OVERDUE"),"due_soon":sum(1 for o in orders if o["deadline_state"]=="DUE_SOON"),"ready_over_2h":sum(1 for o in ready if (o["ready_age_minutes"] or 0)>=120),"ready_unpaid":sum(1 for o in ready if o["payment_status"]!="PAID"),"express":sum(1 for o in orders if o["service_speed"]=="EXPRESS"),"exceptions":len(exceptions)}
    return {"summary":{"active":len(orders),"overdue":handover["overdue"],"due_soon":handover["due_soon"],"ready":handover["ready"],"unpaid":sum(1 for o in orders if o["payment_status"]!="PAID"),"express":handover["express"],"ready_over_2h":handover["ready_over_2h"],"exceptions":handover["exceptions"]},"handover":handover,"exceptions":exceptions[:10],"orders":orders}

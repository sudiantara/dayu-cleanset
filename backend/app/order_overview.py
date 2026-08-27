from fastapi import HTTPException

from app.entrypoint import app
from app.main import get_db_connection


@app.get("/api/orders/{order_number}/overview-v2")
def get_order_overview_v2(order_number: str):
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        o.id,
                        o.order_number,
                        c.id,
                        c.name,
                        c.phone,
                        o.hotel_name,
                        o.room_number,
                        o.location_notes,
                        o.service_speed,
                        o.requested_finish_at,
                        o.status,
                        o.total_weight,
                        o.instagram_followed,
                        o.google_reviewed,
                        o.subtotal,
                        o.promo_discount,
                        o.special_discount,
                        o.special_discount_reason,
                        o.discount,
                        o.total,
                        o.payment_status,
                        o.notes,
                        o.created_at,
                        o.updated_at,
                        o.completed_at
                    FROM orders o
                    JOIN customers c ON c.id = o.customer_id
                    WHERE o.order_number = %s
                    """,
                    (order_number,)
                )
                row = cursor.fetchone()

                if not row:
                    raise HTTPException(status_code=404, detail="Order tidak ditemukan")

                order_id = row[0]

                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.amount,
                        p.payment_method,
                        p.reference_number,
                        p.notes,
                        p.paid_at,
                        u.name
                    FROM payments p
                    LEFT JOIN users u ON u.id = p.created_by
                    WHERE p.order_id = %s
                    ORDER BY p.id DESC
                    """,
                    (order_id,)
                )
                payment_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        h.id,
                        h.status,
                        h.note,
                        h.changed_at,
                        u.name
                    FROM order_status_history h
                    LEFT JOIN users u ON u.id = h.changed_by
                    WHERE h.order_id = %s
                    ORDER BY h.id DESC
                    """,
                    (order_id,)
                )
                history_rows = cursor.fetchall()

        payments = [
            {
                "id": p[0],
                "amount": float(p[1]),
                "payment_method": p[2],
                "reference_number": p[3],
                "notes": p[4],
                "created_at": p[5].isoformat(),
                "operator": p[6],
            }
            for p in payment_rows
        ]

        history = [
            {
                "id": h[0],
                "status": h[1],
                "note": h[2],
                "created_at": h[3].isoformat(),
                "operator": h[4],
            }
            for h in history_rows
        ]

        paid_amount = sum(item["amount"] for item in payments)
        total = float(row[19])

        return {
            "id": order_id,
            "order_number": row[1],
            "customer": {"id": row[2], "name": row[3], "phone": row[4]},
            "location": {
                "hotel_name": row[5],
                "room_number": row[6],
                "location_notes": row[7],
            },
            "service": {
                "speed": row[8],
                "requested_finish_at": row[9].isoformat() if row[9] else None,
                "status": row[10],
                "total_weight": float(row[11]) if row[11] is not None else 0,
            },
            "promo": {
                "instagram_followed": row[12],
                "google_reviewed": row[13],
                "promo_discount": float(row[15]),
                "special_discount": float(row[16]),
                "special_discount_reason": row[17],
            },
            "billing": {
                "subtotal": float(row[14]),
                "discount": float(row[18]),
                "total": total,
                "payment_status": row[20],
                "paid_amount": paid_amount,
                "remaining_amount": max(total - paid_amount, 0),
            },
            "notes": row[21],
            "created_at": row[22].isoformat(),
            "updated_at": row[23].isoformat(),
            "completed_at": row[24].isoformat() if row[24] else None,
            "payments": payments,
            "history": history,
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

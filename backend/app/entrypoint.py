from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from app.main import app, get_db_connection


class CreateCustomerRequest(BaseModel):
    name: str
    phone: str
    address: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/customers", status_code=201)
def create_customer(request: CreateCustomerRequest):
    name = request.name.strip()
    phone = request.phone.strip()
    address = request.address.strip() if request.address else None
    notes = request.notes.strip() if request.notes else None

    if not name:
        raise HTTPException(status_code=400, detail="Nama customer wajib diisi")

    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Nomor WhatsApp / HP wajib diisi"
        )

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, phone
                    FROM customers
                    WHERE LOWER(TRIM(phone)) = LOWER(TRIM(%s))
                    ORDER BY id
                    LIMIT 1
                    """,
                    (phone,)
                )

                existing_customer = cursor.fetchone()

                if existing_customer:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Nomor WhatsApp / HP sudah terdaftar untuk "
                            f"customer {existing_customer[1]}"
                        )
                    )

                cursor.execute(
                    """
                    INSERT INTO customers
                    (
                        name,
                        phone,
                        address,
                        notes
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING
                        id,
                        name,
                        phone,
                        address,
                        notes,
                        created_at
                    """,
                    (name, phone, address, notes)
                )

                customer = cursor.fetchone()

            connection.commit()

        return {
            "status": "success",
            "message": "Customer berhasil dibuat",
            "customer": {
                "id": customer[0],
                "name": customer[1],
                "phone": customer[2],
                "address": customer[3],
                "notes": customer[4],
                "created_at": customer[5].isoformat()
            }
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/api/orders/{order_number}/overview")
def get_order_overview(order_number: str):
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
                    raise HTTPException(
                        status_code=404,
                        detail="Order tidak ditemukan"
                    )

                order_id = row[0]

                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.amount,
                        p.payment_method,
                        p.reference_number,
                        p.notes,
                        p.created_at,
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
                        h.created_at,
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
                "id": payment[0],
                "amount": float(payment[1]),
                "payment_method": payment[2],
                "reference_number": payment[3],
                "notes": payment[4],
                "created_at": payment[5].isoformat(),
                "operator": payment[6]
            }
            for payment in payment_rows
        ]

        history = [
            {
                "id": item[0],
                "status": item[1],
                "note": item[2],
                "created_at": item[3].isoformat(),
                "operator": item[4]
            }
            for item in history_rows
        ]

        return {
            "id": order_id,
            "order_number": row[1],
            "customer": {
                "id": row[2],
                "name": row[3],
                "phone": row[4]
            },
            "location": {
                "hotel_name": row[5],
                "room_number": row[6],
                "location_notes": row[7]
            },
            "service": {
                "speed": row[8],
                "requested_finish_at": (
                    row[9].isoformat() if row[9] else None
                ),
                "status": row[10],
                "total_weight": float(row[11]) if row[11] is not None else 0
            },
            "promo": {
                "instagram_followed": row[12],
                "google_reviewed": row[13],
                "promo_discount": float(row[15]),
                "special_discount": float(row[16]),
                "special_discount_reason": row[17]
            },
            "billing": {
                "subtotal": float(row[14]),
                "discount": float(row[18]),
                "total": float(row[19]),
                "payment_status": row[20],
                "paid_amount": sum(payment["amount"] for payment in payments),
                "remaining_amount": max(
                    float(row[19]) - sum(
                        payment["amount"] for payment in payments
                    ),
                    0
                )
            },
            "notes": row[21],
            "created_at": row[22].isoformat(),
            "updated_at": row[23].isoformat(),
            "completed_at": row[24].isoformat() if row[24] else None,
            "payments": payments,
            "history": history
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

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
        raise HTTPException(
            status_code=400,
            detail="Nama customer wajib diisi"
        )

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
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING
                        id,
                        name,
                        phone,
                        address,
                        notes,
                        created_at
                    """,
                    (
                        name,
                        phone,
                        address,
                        notes
                    )
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
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

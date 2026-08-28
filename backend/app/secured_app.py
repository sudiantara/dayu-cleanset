import json
from datetime import date
from typing import Optional

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from app.auth_app import COOKIE_NAME, _load_active_user, app, parse_session_token
from app.main import get_db_connection


class UpdateCustomerRequest(BaseModel):
    name: str
    phone: str
    address: Optional[str] = None
    notes: Optional[str] = None


class ExpenseRequest(BaseModel):
    category: str
    description: str
    amount: float
    expense_date: date
    notes: Optional[str] = None


def _request_user(request: Request):
    token=request.cookies.get(COOKIE_NAME)
    if not token: raise HTTPException(status_code=401,detail="Silakan login")
    try: return _load_active_user(int(parse_session_token(token)["uid"]))
    except Exception: raise HTTPException(status_code=401,detail="Sesi login tidak valid")


def required_roles(path:str,method:str):
    method=method.upper()
    if path.startswith("/api/admin/users"): return {"ADMIN"}
    if path.startswith("/api/expenses") and method in {"POST","PATCH"}: return {"ADMIN","KASIR"}
    if path.startswith("/api/expenses") and method=="DELETE": return {"ADMIN"}
    if path.startswith("/api/customers/") and method=="DELETE": return {"ADMIN"}
    if path.startswith("/api/customers/") and method=="PATCH": return {"ADMIN","KASIR"}
    if method=="DELETE" and path.startswith("/api/orders/"): return {"ADMIN"}
    if method=="POST" and path.rstrip("/")=="/api/customers": return {"ADMIN","KASIR"}
    if path.startswith("/api/orders"):
        if method=="POST" and path.rstrip("/")=="/api/orders": return {"ADMIN","KASIR"}
        if "/payments" in path or path.endswith("/mark-paid"): return {"ADMIN","KASIR"}
        if path.endswith("/edit-v2"): return {"ADMIN","KASIR"}
        if path.endswith("/status-v2") or path.endswith("/status"): return {"ADMIN","KASIR","STAFF"}
    return None


@app.middleware("http")
async def strict_role_middleware(request:Request,call_next):
    allowed=required_roles(request.url.path,request.method)
    if not allowed:return await call_next(request)
    token=request.cookies.get(COOKIE_NAME)
    if not token:return Response(content=json.dumps({"detail":"Silakan login"}),status_code=401,media_type="application/json")
    try:user=_load_active_user(int(parse_session_token(token)["uid"]))
    except Exception:return Response(content=json.dumps({"detail":"Sesi login tidak valid"}),status_code=401,media_type="application/json")
    if user["role"] not in allowed:return Response(content=json.dumps({"detail":"Role user tidak memiliki izin untuk aksi ini"}),status_code=403,media_type="application/json")
    return await call_next(request)


@app.get("/api/business-dashboard-v1")
def business_dashboard_v1():
    with get_db_connection() as c:
        with c.cursor() as x:
            x.execute("SELECT COALESCE(SUM(amount),0),COALESCE(SUM(amount) FILTER(WHERE paid_at::date=CURRENT_DATE),0),COALESCE(SUM(amount) FILTER(WHERE paid_at>=date_trunc('month',CURRENT_DATE)),0) FROM payments"); ia,it,im=x.fetchone()
            x.execute("SELECT COALESCE(SUM(amount),0),COALESCE(SUM(amount) FILTER(WHERE expense_date=CURRENT_DATE),0),COALESCE(SUM(amount) FILTER(WHERE expense_date>=date_trunc('month',CURRENT_DATE)::date),0) FROM expenses"); ea,et,em=x.fetchone()
            x.execute("SELECT COALESCE(SUM(total_weight) FILTER(WHERE created_at::date=CURRENT_DATE),0),COALESCE(SUM(total_weight) FILTER(WHERE created_at>=CURRENT_DATE-INTERVAL '6 days'),0),COALESCE(SUM(total_weight),0),COUNT(*) FILTER(WHERE created_at::date=CURRENT_DATE),COUNT(*) FILTER(WHERE status NOT IN('COMPLETE','PICKED_UP','CANCELLED')),COUNT(*) FILTER(WHERE payment_status<>'PAID') FROM orders"); kt,k7,ka,ot,oa,ou=x.fetchone()
    return {"income":{"today":float(it),"month":float(im),"all_time":float(ia)},"expense":{"today":float(et),"month":float(em),"all_time":float(ea)},"net_profit":{"today":float(it-et),"month":float(im-em),"all_time":float(ia-ea)},"weight_kg":{"today":float(kt),"last_7_days":float(k7),"all_time":float(ka)},"orders":{"today":ot,"active":oa,"unpaid":ou}}


@app.get("/api/finance-report-v1")
def finance_report_v1():
    with get_db_connection() as c:
        with c.cursor() as x:
            x.execute("""WITH d AS (SELECT generate_series(CURRENT_DATE-INTERVAL '29 days',CURRENT_DATE,INTERVAL '1 day')::date day), p AS (SELECT paid_at::date day,SUM(amount) income FROM payments WHERE paid_at>=CURRENT_DATE-INTERVAL '29 days' GROUP BY 1), e AS (SELECT expense_date day,SUM(amount) expense FROM expenses WHERE expense_date>=CURRENT_DATE-INTERVAL '29 days' GROUP BY 1), o AS (SELECT created_at::date day,COUNT(*) orders,COALESCE(SUM(total_weight),0) kg FROM orders WHERE created_at>=CURRENT_DATE-INTERVAL '29 days' GROUP BY 1) SELECT d.day,COALESCE(p.income,0),COALESCE(e.expense,0),COALESCE(o.orders,0),COALESCE(o.kg,0) FROM d LEFT JOIN p USING(day) LEFT JOIN e USING(day) LEFT JOIN o USING(day) ORDER BY d.day"""); daily=x.fetchall()
            x.execute("""WITH m AS (SELECT generate_series(date_trunc('month',CURRENT_DATE)-INTERVAL '11 months',date_trunc('month',CURRENT_DATE),INTERVAL '1 month')::date month), p AS (SELECT date_trunc('month',paid_at)::date month,SUM(amount) income FROM payments WHERE paid_at>=date_trunc('month',CURRENT_DATE)-INTERVAL '11 months' GROUP BY 1), e AS (SELECT date_trunc('month',expense_date)::date month,SUM(amount) expense FROM expenses WHERE expense_date>=date_trunc('month',CURRENT_DATE)-INTERVAL '11 months' GROUP BY 1), o AS (SELECT date_trunc('month',created_at)::date month,COUNT(*) orders,COALESCE(SUM(total_weight),0) kg FROM orders WHERE created_at>=date_trunc('month',CURRENT_DATE)-INTERVAL '11 months' GROUP BY 1) SELECT m.month,COALESCE(p.income,0),COALESCE(e.expense,0),COALESCE(o.orders,0),COALESCE(o.kg,0) FROM m LEFT JOIN p USING(month) LEFT JOIN e USING(month) LEFT JOIN o USING(month) ORDER BY m.month"""); monthly=x.fetchall()
            x.execute("SELECT payment_method,COUNT(*),COALESCE(SUM(amount),0) FROM payments WHERE paid_at>=date_trunc('month',CURRENT_DATE) GROUP BY payment_method ORDER BY SUM(amount) DESC"); methods=x.fetchall()
            x.execute("SELECT category,COUNT(*),COALESCE(SUM(amount),0) FROM expenses WHERE expense_date>=date_trunc('month',CURRENT_DATE)::date GROUP BY category ORDER BY SUM(amount) DESC"); cats=x.fetchall()
    def rows(data):return [{"period":r[0].isoformat(),"income":float(r[1]),"expense":float(r[2]),"profit":float(r[1]-r[2]),"orders":r[3],"kg":float(r[4])} for r in data]
    return {"daily":rows(daily),"monthly":rows(monthly),"payment_methods":[{"name":r[0],"transactions":r[1],"amount":float(r[2])} for r in methods],"expense_categories":[{"name":r[0],"transactions":r[1],"amount":float(r[2])} for r in cats]}


@app.get("/api/expenses-v1")
def list_expenses_v1():
    with get_db_connection() as c:
        with c.cursor() as x:x.execute("SELECT e.id,e.category,e.description,e.amount,e.expense_date,e.notes,e.created_at,e.updated_at,u.name FROM expenses e LEFT JOIN users u ON u.id=e.created_by ORDER BY e.expense_date DESC,e.id DESC");rows=x.fetchall()
    return [{"id":r[0],"category":r[1],"description":r[2],"amount":float(r[3]),"expense_date":r[4].isoformat(),"notes":r[5],"created_at":r[6].isoformat(),"updated_at":r[7].isoformat(),"created_by":r[8]} for r in rows]


@app.post("/api/expenses-v1")
def create_expense_v1(payload:ExpenseRequest,request:Request):
    user=_request_user(request);cat,desc=payload.category.strip(),payload.description.strip()
    if not cat or not desc or payload.amount<=0:raise HTTPException(status_code=400,detail="Kategori, keterangan, dan nominal wajib valid")
    with get_db_connection() as c:
        with c.cursor() as x:x.execute("INSERT INTO expenses(category,description,amount,expense_date,notes,created_by) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",(cat,desc,payload.amount,payload.expense_date,payload.notes,user["id"]));eid=x.fetchone()[0]
        c.commit()
    return {"status":"success","id":eid}


@app.patch("/api/expenses-v1/{expense_id}")
def update_expense_v1(expense_id:int,payload:ExpenseRequest):
    cat,desc=payload.category.strip(),payload.description.strip()
    if not cat or not desc or payload.amount<=0:raise HTTPException(status_code=400,detail="Kategori, keterangan, dan nominal wajib valid")
    with get_db_connection() as c:
        with c.cursor() as x:x.execute("UPDATE expenses SET category=%s,description=%s,amount=%s,expense_date=%s,notes=%s,updated_at=NOW() WHERE id=%s RETURNING id",(cat,desc,payload.amount,payload.expense_date,payload.notes,expense_id));found=x.fetchone()
        if not found:raise HTTPException(status_code=404,detail="Pengeluaran tidak ditemukan")
        c.commit()
    return {"status":"success"}


@app.delete("/api/expenses-v1/{expense_id}")
def delete_expense_v1(expense_id:int):
    with get_db_connection() as c:
        with c.cursor() as x:x.execute("DELETE FROM expenses WHERE id=%s RETURNING id",(expense_id,));found=x.fetchone()
        if not found:raise HTTPException(status_code=404,detail="Pengeluaran tidak ditemukan")
        c.commit()
    return {"status":"success"}


@app.get("/api/orders-list-v2")
def get_orders_list_v2():
    with get_db_connection() as c:
        with c.cursor() as x:x.execute("SELECT o.id,o.order_number,c.name,c.phone,o.hotel_name,o.room_number,o.service_speed,o.status,o.total_weight,o.subtotal,o.discount,o.total,o.payment_status,o.requested_finish_at,o.created_at,u.name FROM orders o JOIN customers c ON c.id=o.customer_id LEFT JOIN users u ON u.id=o.created_by ORDER BY o.id DESC");rows=x.fetchall()
    return [{"id":r[0],"order_number":r[1],"customer":r[2],"phone":r[3],"hotel_name":r[4],"room_number":r[5],"service_speed":r[6],"status":r[7],"total_weight":float(r[8] or 0),"subtotal":float(r[9]),"discount":float(r[10]),"total":float(r[11]),"payment_status":r[12],"requested_finish_at":r[13].isoformat() if r[13] else None,"created_at":r[14].isoformat(),"received_by":r[15]} for r in rows]


@app.get("/api/customers-list-v2")
def get_customers_list_v2():
    with get_db_connection() as c:
        with c.cursor() as x:x.execute("SELECT c.id,c.name,c.phone,c.address,c.notes,c.created_at,COUNT(o.id),COALESCE(SUM(o.total),0),MAX(o.created_at) FROM customers c LEFT JOIN orders o ON o.customer_id=c.id GROUP BY c.id,c.name,c.phone,c.address,c.notes,c.created_at ORDER BY c.id DESC");rows=x.fetchall()
    return [{"id":r[0],"name":r[1],"phone":r[2],"address":r[3],"notes":r[4],"created_at":r[5].isoformat(),"order_count":r[6],"lifetime_value":float(r[7]),"last_order_at":r[8].isoformat() if r[8] else None} for r in rows]


@app.get("/api/customers/{customer_id}/orders-v2")
def get_customer_orders_v2(customer_id:int):
    with get_db_connection() as c:
        with c.cursor() as x:
            x.execute("SELECT id,name,phone FROM customers WHERE id=%s",(customer_id,));customer=x.fetchone()
            if not customer:raise HTTPException(status_code=404,detail="Customer tidak ditemukan")
            x.execute("SELECT order_number,status,payment_status,service_speed,total_weight,total,hotel_name,room_number,created_at FROM orders WHERE customer_id=%s ORDER BY id DESC",(customer_id,));rows=x.fetchall()
    return {"customer":{"id":customer[0],"name":customer[1],"phone":customer[2]},"orders":[{"order_number":r[0],"status":r[1],"payment_status":r[2],"service_speed":r[3],"total_weight":float(r[4] or 0),"total":float(r[5]),"hotel_name":r[6],"room_number":r[7],"created_at":r[8].isoformat()} for r in rows]}


@app.patch("/api/customers/{customer_id}")
def update_customer_v2(customer_id:int,payload:UpdateCustomerRequest):
    name,phone=payload.name.strip(),payload.phone.strip()
    if not name or not phone:raise HTTPException(status_code=400,detail="Nama dan nomor HP wajib diisi")
    with get_db_connection() as c:
        with c.cursor() as x:
            x.execute("SELECT id FROM customers WHERE LOWER(TRIM(phone))=LOWER(TRIM(%s)) AND id<>%s LIMIT 1",(phone,customer_id))
            if x.fetchone():raise HTTPException(status_code=409,detail="Nomor WhatsApp / HP sudah digunakan customer lain")
            x.execute("UPDATE customers SET name=%s,phone=%s,address=%s,notes=%s,updated_at=NOW() WHERE id=%s RETURNING id,name,phone,address,notes,updated_at",(name,phone,payload.address,payload.notes,customer_id));r=x.fetchone()
            if not r:raise HTTPException(status_code=404,detail="Customer tidak ditemukan")
        c.commit()
    return {"id":r[0],"name":r[1],"phone":r[2],"address":r[3],"notes":r[4],"updated_at":r[5].isoformat()}


@app.delete("/api/customers/{customer_id}")
def delete_customer_v2(customer_id:int):
    with get_db_connection() as c:
        with c.cursor() as x:
            x.execute("SELECT COUNT(*) FROM orders WHERE customer_id=%s",(customer_id,));count=x.fetchone()[0]
            if count:raise HTTPException(status_code=409,detail=f"Customer memiliki {count} order dan tidak boleh dihapus")
            x.execute("DELETE FROM customers WHERE id=%s RETURNING id",(customer_id,));found=x.fetchone()
            if not found:raise HTTPException(status_code=404,detail="Customer tidak ditemukan")
        c.commit()
    return {"status":"success"}


@app.get("/api/payments-list-v2")
def get_payments_list_v2():
    with get_db_connection() as c:
        with c.cursor() as x:x.execute("SELECT p.id,o.order_number,c.name,c.phone,p.amount,p.payment_method,p.reference_number,p.notes,p.paid_at,u.name FROM payments p JOIN orders o ON o.id=p.order_id JOIN customers c ON c.id=o.customer_id LEFT JOIN users u ON u.id=p.created_by ORDER BY p.paid_at DESC,p.id DESC");rows=x.fetchall()
    return [{"id":r[0],"order_number":r[1],"customer":r[2],"phone":r[3],"amount":float(r[4]),"payment_method":r[5],"reference_number":r[6],"notes":r[7],"paid_at":r[8].isoformat(),"operator":r[9]} for r in rows]


@app.get("/api/service-config-v2")
def get_service_config_v2():
    return {"normal":{"name":"NORMAL","price_per_kg":30000,"sla":"Maksimal 1 hari"},"express":{"name":"EXPRESS","price_per_kg":55000,"sla":"Di bawah 6 jam"},"promo":{"percent":5,"require_instagram":True,"require_google_review":True,"description":"Promo 5% berlaku jika customer follow Instagram dan review Google Maps."}}

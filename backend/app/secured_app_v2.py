import json
from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException, Request, Response

from app.secured_app import app
from app.main import get_db_connection
from app.auth_app import COOKIE_NAME, _load_active_user, parse_session_token


FINANCE_PREFIXES = (
    "/api/business-dashboard",
    "/api/finance-report",
    "/api/finance-period",
    "/api/expenses",
)


@app.middleware("http")
async def finance_admin_only_middleware(request: Request, call_next):
    if not request.url.path.startswith(FINANCE_PREFIXES):
        return await call_next(request)
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return Response(content=json.dumps({"detail": "Silakan login"}), status_code=401, media_type="application/json")
    try:
        user = _load_active_user(int(parse_session_token(token)["uid"]))
    except Exception:
        return Response(content=json.dumps({"detail": "Sesi login tidak valid"}), status_code=401, media_type="application/json")
    if user["role"] != "ADMIN":
        return Response(content=json.dumps({"detail": "Keuangan hanya dapat diakses ADMIN"}), status_code=403, media_type="application/json")
    return await call_next(request)


def _date_rows(start_date, end_date, income_map, expense_map, order_map):
    rows = []
    cursor_date = start_date
    while cursor_date <= end_date:
        income = income_map.get(cursor_date, 0.0)
        expense = expense_map.get(cursor_date, 0.0)
        orders, kg = order_map.get(cursor_date, (0, 0.0))
        rows.append({"period": cursor_date.isoformat(), "income": income, "expense": expense, "profit": income - expense, "orders": orders, "kg": kg})
        cursor_date += timedelta(days=1)
    return rows


@app.get("/api/finance-period-v1")
def finance_period_v1(start_date: Optional[date] = None, end_date: Optional[date] = None):
    end_date = end_date or date.today()
    start_date = start_date or end_date.replace(day=1)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Tanggal mulai tidak boleh lebih besar dari tanggal akhir")
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=400, detail="Rentang laporan maksimal 367 hari")

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT paid_at::date, COALESCE(SUM(amount),0) FROM payments WHERE paid_at::date BETWEEN %s AND %s GROUP BY 1 ORDER BY 1", (start_date, end_date))
            income_map = {r[0]: float(r[1]) for r in cursor.fetchall()}
            cursor.execute("SELECT expense_date, COALESCE(SUM(amount),0) FROM expenses WHERE expense_date BETWEEN %s AND %s GROUP BY 1 ORDER BY 1", (start_date, end_date))
            expense_map = {r[0]: float(r[1]) for r in cursor.fetchall()}
            cursor.execute("SELECT created_at::date, COUNT(*), COALESCE(SUM(total_weight),0) FROM orders WHERE created_at::date BETWEEN %s AND %s GROUP BY 1 ORDER BY 1", (start_date, end_date))
            order_map = {r[0]: (r[1], float(r[2])) for r in cursor.fetchall()}
            cursor.execute("SELECT payment_method, COUNT(*), COALESCE(SUM(amount),0) FROM payments WHERE paid_at::date BETWEEN %s AND %s GROUP BY payment_method ORDER BY SUM(amount) DESC", (start_date, end_date))
            methods = cursor.fetchall()
            cursor.execute("SELECT category, COUNT(*), COALESCE(SUM(amount),0) FROM expenses WHERE expense_date BETWEEN %s AND %s GROUP BY category ORDER BY SUM(amount) DESC", (start_date, end_date))
            categories = cursor.fetchall()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_weight),0), COUNT(*) FILTER (WHERE payment_status <> 'PAID') FROM orders WHERE created_at::date BETWEEN %s AND %s", (start_date, end_date))
            order_count, kg_total, unpaid_orders = cursor.fetchone()

    rows = _date_rows(start_date, end_date, income_map, expense_map, order_map)
    income = sum(r["income"] for r in rows)
    expense = sum(r["expense"] for r in rows)
    best_day = max(rows, key=lambda r: r["income"], default=None)
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": len(rows),
        "summary": {
            "income": income,
            "expense": expense,
            "profit": income - expense,
            "orders": order_count,
            "kg": float(kg_total or 0),
            "unpaid_orders": unpaid_orders,
            "avg_income_per_day": income / len(rows) if rows else 0,
            "avg_kg_per_day": float(kg_total or 0) / len(rows) if rows else 0,
            "best_income_day": best_day,
        },
        "daily": rows,
        "payment_methods": [{"name": r[0], "transactions": r[1], "amount": float(r[2])} for r in methods],
        "expense_categories": [{"name": r[0], "transactions": r[1], "amount": float(r[2])} for r in categories],
    }


@app.get("/api/finance-report-v2")
def finance_report_v2():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT CURRENT_DATE")
            current_date = cursor.fetchone()[0]
            start_daily = current_date - timedelta(days=29)
            cursor.execute("SELECT paid_at::date, COALESCE(SUM(amount),0) FROM payments WHERE paid_at::date BETWEEN %s AND %s GROUP BY 1", (start_daily, current_date)); daily_income={r[0]:float(r[1]) for r in cursor.fetchall()}
            cursor.execute("SELECT expense_date, COALESCE(SUM(amount),0) FROM expenses WHERE expense_date BETWEEN %s AND %s GROUP BY 1", (start_daily, current_date)); daily_expense={r[0]:float(r[1]) for r in cursor.fetchall()}
            cursor.execute("SELECT created_at::date, COUNT(*), COALESCE(SUM(total_weight),0) FROM orders WHERE created_at::date BETWEEN %s AND %s GROUP BY 1", (start_daily, current_date)); daily_orders={r[0]:(r[1],float(r[2])) for r in cursor.fetchall()}
            cursor.execute("SELECT date_trunc('month',paid_at)::date,COALESCE(SUM(amount),0) FROM payments WHERE paid_at>=date_trunc('month',CURRENT_DATE)-INTERVAL '11 months' GROUP BY 1"); monthly_income={r[0]:float(r[1]) for r in cursor.fetchall()}
            cursor.execute("SELECT date_trunc('month',expense_date::timestamp)::date,COALESCE(SUM(amount),0) FROM expenses WHERE expense_date>=(date_trunc('month',CURRENT_DATE)-INTERVAL '11 months')::date GROUP BY 1"); monthly_expense={r[0]:float(r[1]) for r in cursor.fetchall()}
            cursor.execute("SELECT date_trunc('month',created_at)::date,COUNT(*),COALESCE(SUM(total_weight),0) FROM orders WHERE created_at>=date_trunc('month',CURRENT_DATE)-INTERVAL '11 months' GROUP BY 1"); monthly_orders={r[0]:(r[1],float(r[2])) for r in cursor.fetchall()}
            cursor.execute("SELECT payment_method,COUNT(*),COALESCE(SUM(amount),0) FROM payments WHERE paid_at>=date_trunc('month',CURRENT_DATE) GROUP BY payment_method ORDER BY SUM(amount) DESC"); payment_methods=cursor.fetchall()
            cursor.execute("SELECT category,COUNT(*),COALESCE(SUM(amount),0) FROM expenses WHERE expense_date>=date_trunc('month',CURRENT_DATE)::date GROUP BY category ORDER BY SUM(amount) DESC"); expense_categories=cursor.fetchall()

    daily = _date_rows(start_daily, current_date, daily_income, daily_expense, daily_orders)
    def month_shift(base, back):
        y, m = base.year, base.month - back
        while m <= 0: m += 12; y -= 1
        return base.replace(year=y, month=m, day=1)
    monthly=[]
    for offset in range(11,-1,-1):
        period=month_shift(current_date.replace(day=1),offset); income=monthly_income.get(period,0.0); expense=monthly_expense.get(period,0.0); orders,kg=monthly_orders.get(period,(0,0.0)); monthly.append({"period":period.isoformat(),"income":income,"expense":expense,"profit":income-expense,"orders":orders,"kg":kg})
    return {"daily":daily,"monthly":monthly,"payment_methods":[{"name":r[0],"transactions":r[1],"amount":float(r[2])} for r in payment_methods],"expense_categories":[{"name":r[0],"transactions":r[1],"amount":float(r[2])} for r in expense_categories]}

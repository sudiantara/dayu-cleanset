from app.secured_app import app
from app.main import get_db_connection


@app.get("/api/finance-report-v2")
def finance_report_v2():
    """Stable finance reporting endpoint for Step 23C.

    Uses separate grouped queries and fills missing periods in Python to avoid
    complex PostgreSQL generate_series/USING joins causing report failures.
    """
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT paid_at::date AS period, COALESCE(SUM(amount), 0)
                FROM payments
                WHERE paid_at::date >= CURRENT_DATE - 29
                GROUP BY paid_at::date
                ORDER BY period
                """
            )
            daily_income = {row[0]: float(row[1]) for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT expense_date AS period, COALESCE(SUM(amount), 0)
                FROM expenses
                WHERE expense_date >= CURRENT_DATE - 29
                GROUP BY expense_date
                ORDER BY period
                """
            )
            daily_expense = {row[0]: float(row[1]) for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT created_at::date AS period, COUNT(*), COALESCE(SUM(total_weight), 0)
                FROM orders
                WHERE created_at::date >= CURRENT_DATE - 29
                GROUP BY created_at::date
                ORDER BY period
                """
            )
            daily_orders = {row[0]: (row[1], float(row[2])) for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT date_trunc('month', paid_at)::date AS period, COALESCE(SUM(amount), 0)
                FROM payments
                WHERE paid_at >= date_trunc('month', CURRENT_DATE) - INTERVAL '11 months'
                GROUP BY date_trunc('month', paid_at)::date
                ORDER BY period
                """
            )
            monthly_income = {row[0]: float(row[1]) for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT date_trunc('month', expense_date::timestamp)::date AS period, COALESCE(SUM(amount), 0)
                FROM expenses
                WHERE expense_date >= (date_trunc('month', CURRENT_DATE) - INTERVAL '11 months')::date
                GROUP BY date_trunc('month', expense_date::timestamp)::date
                ORDER BY period
                """
            )
            monthly_expense = {row[0]: float(row[1]) for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT date_trunc('month', created_at)::date AS period, COUNT(*), COALESCE(SUM(total_weight), 0)
                FROM orders
                WHERE created_at >= date_trunc('month', CURRENT_DATE) - INTERVAL '11 months'
                GROUP BY date_trunc('month', created_at)::date
                ORDER BY period
                """
            )
            monthly_orders = {row[0]: (row[1], float(row[2])) for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT payment_method, COUNT(*), COALESCE(SUM(amount), 0)
                FROM payments
                WHERE paid_at >= date_trunc('month', CURRENT_DATE)
                GROUP BY payment_method
                ORDER BY SUM(amount) DESC
                """
            )
            payment_methods = cursor.fetchall()

            cursor.execute(
                """
                SELECT category, COUNT(*), COALESCE(SUM(amount), 0)
                FROM expenses
                WHERE expense_date >= date_trunc('month', CURRENT_DATE)::date
                GROUP BY category
                ORDER BY SUM(amount) DESC
                """
            )
            expense_categories = cursor.fetchall()

            cursor.execute("SELECT CURRENT_DATE")
            current_date = cursor.fetchone()[0]

    from datetime import timedelta

    daily = []
    for offset in range(29, -1, -1):
        period = current_date - timedelta(days=offset)
        income = daily_income.get(period, 0.0)
        expense = daily_expense.get(period, 0.0)
        orders, kg = daily_orders.get(period, (0, 0.0))
        daily.append({
            "period": period.isoformat(),
            "income": income,
            "expense": expense,
            "profit": income - expense,
            "orders": orders,
            "kg": kg,
        })

    def month_shift(base, months_back):
        year = base.year
        month = base.month - months_back
        while month <= 0:
            month += 12
            year -= 1
        return base.replace(year=year, month=month, day=1)

    monthly = []
    for offset in range(11, -1, -1):
        period = month_shift(current_date.replace(day=1), offset)
        income = monthly_income.get(period, 0.0)
        expense = monthly_expense.get(period, 0.0)
        orders, kg = monthly_orders.get(period, (0, 0.0))
        monthly.append({
            "period": period.isoformat(),
            "income": income,
            "expense": expense,
            "profit": income - expense,
            "orders": orders,
            "kg": kg,
        })

    return {
        "daily": daily,
        "monthly": monthly,
        "payment_methods": [
            {"name": row[0], "transactions": row[1], "amount": float(row[2])}
            for row in payment_methods
        ],
        "expense_categories": [
            {"name": row[0], "transactions": row[1], "amount": float(row[2])}
            for row in expense_categories
        ],
    }

from __future__ import annotations
import asyncio
import logging
import calendar
from datetime import date
from sqlalchemy import select, extract
from db.models import Order, User, DailyStat
from db.connection import async_session_maker
from config import settings

log = logging.getLogger(__name__)

MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь",
             "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
TEAM_ORDER = ["Тапок", "СС", "Танк", "Без команды"]
DELIVERY_FEE = 10.0
DAY_RU = ["Пн", "Вт", "Ср", "Чт", "Пт"]


async def generate_monthly_report(month: int, year: int) -> str:
    data = await _fetch_report_data(month, year)
    url = await asyncio.to_thread(_create_spreadsheet, data, month, year)
    return url


async def _fetch_report_data(month: int, year: int) -> dict:
    async with async_session_maker() as session:
        emp_res = await session.execute(
            select(User).where(User.is_active == True, User.role == "employee")
        )
        all_employees = emp_res.scalars().all()

        ord_res = await session.execute(
            select(Order).where(
                extract("month", Order.order_date) == month,
                extract("year", Order.order_date) == year,
                Order.status != "cancelled",
            )
        )
        orders = ord_res.scalars().all()

        stat_res = await session.execute(
            select(DailyStat).where(
                extract("month", DailyStat.order_date) == month,
                extract("year", DailyStat.order_date) == year,
            )
        )
        stats = stat_res.scalars().all()

    # (user_id, date) -> food sum (delivery добавляем при отображении)
    order_lookup: dict[tuple[int, date], float] = {}
    for order in orders:
        key = (order.user_id, order.order_date)
        order_lookup[key] = order_lookup.get(key, 0.0) + float(order.total_price)

    taxi_lookup: dict[date, float] = {s.order_date: float(s.taxi_cost) for s in stats}

    return {
        "employees": [
            {"id": e.id, "name": e.full_name, "team": e.team or "Без команды"}
            for e in all_employees
        ],
        "order_lookup": order_lookup,
        "taxi_lookup": taxi_lookup,
    }


def _create_spreadsheet(data: dict, month: int, year: int) -> str:
    try:
        import gspread
    except ImportError:
        raise RuntimeError("Библиотека gspread не установлена")

    try:
        gc = gspread.service_account(filename=settings.GOOGLE_CREDENTIALS_FILE)
    except FileNotFoundError:
        raise RuntimeError(f"Файл не найден: {settings.GOOGLE_CREDENTIALS_FILE}")
    except Exception as e:
        raise RuntimeError(f"Не удалось подключиться к Google: {e}")

    if not settings.GOOGLE_REPORT_SHEET_ID:
        raise RuntimeError("Задай GOOGLE_REPORT_SHEET_ID в .env")

    employees: list[dict] = data["employees"]
    order_lookup: dict[tuple[int, date], float] = data["order_lookup"]
    taxi_lookup: dict[date, float] = data.get("taxi_lookup", {})

    # Рабочие дни месяца (пн–сб, если суббота в заказах)
    num_days_in_month = calendar.monthrange(year, month)[1]
    sat_with_orders = {d for (_, d) in order_lookup if d.weekday() == 5}
    workdays = [
        date(year, month, d)
        for d in range(1, num_days_in_month + 1)
        if date(year, month, d).weekday() < 5
        or date(year, month, d) in sat_with_orders
    ]
    n_days = len(workdays)
    n_cols = n_days + 2  # имя + дни + тотал

    sheet_title = f"{MONTHS_RU[month-1]} {year}"
    try:
        sh = gc.open_by_key(settings.GOOGLE_REPORT_SHEET_ID)
        try:
            ws = sh.worksheet(sheet_title)
            sh.del_worksheet(ws)
        except gspread.WorksheetNotFound:
            pass
        n_rows = len(employees) + len(TEAM_ORDER) * 4 + 20
        ws = sh.add_worksheet(title=sheet_title, rows=max(n_rows, 100), cols=n_cols)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Не удалось открыть таблицу: {e}")

    # ── Строим данные ─────────────────────────────────────────────────────────

    all_rows: list[list] = []
    row_meta: list[dict] = []

    def add(row: list, rtype: str, **kw):
        all_rows.append(row)
        row_meta.append({"type": rtype, **kw})

    # Заголовок
    header = (
        ["Сотрудник"]
        + [f"{DAY_RU[d.weekday()]} {d.day:02d}.{d.month:02d}" for d in workdays]
        + ["Тотал мес"]
    )
    add(header, "header")

    # Группируем сотрудников по командам
    by_team: dict[str, list[dict]] = {}
    for e in employees:
        by_team.setdefault(e["team"], []).append(e)

    ordered_teams = [t for t in TEAM_ORDER if t in by_team]
    for t in sorted(by_team):
        if t not in ordered_teams:
            ordered_teams.append(t)

    grand_total = 0.0
    n_delivery_days = len(order_lookup)

    for team in ordered_teams:
        team_emps = sorted(by_team[team], key=lambda x: x["name"])

        add([f"Команда: {team}"] + [""] * (n_cols - 1), "team_header")

        day_sums = [0.0] * n_days
        team_sum = 0.0

        for emp in team_emps:
            row = [emp["name"]]
            emp_sum = 0.0
            for i, d in enumerate(workdays):
                key = (emp["id"], d)
                if key in order_lookup:
                    val = order_lookup[key] + DELIVERY_FEE
                    row.append(int(round(val)))
                    emp_sum += val
                    day_sums[i] += val
                else:
                    row.append("")
            row.append(int(round(emp_sum)))
            add(row, "employee", has_orders=emp_sum > 0)
            team_sum += emp_sum

        team_row = [f"Итого {team}"]
        for s in day_sums:
            team_row.append(int(round(s)) if s > 0 else "")
        team_row.append(int(round(team_sum)))
        add(team_row, "team_total")
        add([""] * n_cols, "blank")

        grand_total += team_sum

    # Per-day totals from order_lookup
    workdays_idx = {d: i for i, d in enumerate(workdays)}
    global_day_food = [0.0] * n_days
    global_day_orders = [0] * n_days
    for (uid, d), food in order_lookup.items():
        if d in workdays_idx:
            idx = workdays_idx[d]
            global_day_food[idx] += food
            global_day_orders[idx] += 1

    day_food_row = ["Итого за день (еда)"]
    day_del_row = ["Итого за день (с доставкой)"]
    day_food_sum = 0.0
    day_del_sum = 0.0
    for i in range(n_days):
        if global_day_orders[i] > 0:
            f = global_day_food[i]
            t = f + global_day_orders[i] * DELIVERY_FEE
            day_food_row.append(int(round(f)))
            day_del_row.append(int(round(t)))
            day_food_sum += f
            day_del_sum += t
        else:
            day_food_row.append("")
            day_del_row.append("")
    day_food_row.append(int(round(day_food_sum)))
    day_del_row.append(int(round(day_del_sum)))

    day_count_row = ["Кол-во заказов"]
    for i in range(n_days):
        day_count_row.append(global_day_orders[i] if global_day_orders[i] > 0 else "")
    day_count_row.append(sum(global_day_orders))

    taxi_row = ["Такси"]
    taxi_month_total = 0.0
    for d in workdays:
        t = taxi_lookup.get(d, 0.0)
        taxi_row.append(int(round(t)) if t > 0 else "")
        taxi_month_total += t
    taxi_row.append(int(round(taxi_month_total)) if taxi_month_total > 0 else "")

    grand_food = grand_total - n_delivery_days * DELIVERY_FEE

    add([""] * n_cols, "blank")
    add(day_count_row, "day_count")
    add(day_food_row, "day_total")
    add(day_del_row, "day_total_delivery")
    add(taxi_row, "taxi")

    delivery_row = ["Доставка"]
    delivery_month_total = 0.0
    for i in range(n_days):
        if global_day_orders[i] > 0:
            d_fee = int(round(global_day_orders[i] * DELIVERY_FEE))
            delivery_row.append(d_fee)
            delivery_month_total += d_fee
        else:
            delivery_row.append("")
    delivery_row.append(int(round(delivery_month_total)))
    add(delivery_row, "day_total_delivery")

    # ── Запись в таблицу ──────────────────────────────────────────────────────

    ws.append_rows(all_rows, value_input_option="USER_ENTERED")

    sheet_id = ws.id
    requests = []

    for i, meta in enumerate(row_meta):
        t = meta["type"]
        if t == "header":
            requests.append(_fmt_row(sheet_id, i, bg=(0.2, 0.51, 0.85), bold=True, font_size=10))
        elif t == "team_header":
            requests.append(_fmt_row(sheet_id, i, bg=(0.7, 0.7, 0.7), bold=True))
        elif t == "team_total":
            requests.append(_fmt_row(sheet_id, i, bg=(1.0, 0.9, 0.55), bold=True))
        elif t == "day_count":
            requests.append(_fmt_row(sheet_id, i, bg=(0.68, 0.85, 0.95), bold=True))
        elif t == "taxi":
            requests.append(_fmt_row(sheet_id, i, bg=(1.0, 0.85, 0.4), bold=True))
        elif t == "day_total":
            requests.append(_fmt_row(sheet_id, i, bg=(0.76, 0.93, 0.78), bold=True))
        elif t == "day_total_delivery":
            requests.append(_fmt_row(sheet_id, i, bg=(0.34, 0.73, 0.54), bold=True))
        elif t == "grand_total":
            requests.append(_fmt_row(sheet_id, i, bg=(1.0, 0.75, 0.4), bold=True))
        elif t == "employee" and not meta.get("has_orders"):
            # Красный тотал для сотрудников без заказов
            requests.append(_fmt_cell(sheet_id, i, n_cols - 1, bg=(1.0, 0.6, 0.6)))

    # Ширина столбцов
    for col_idx, px in enumerate([200] + [48] * n_days + [90]):
        requests.append(_col_width(sheet_id, col_idx, px))

    # Толстые границы между неделями
    prev_week = None
    for i, d in enumerate(workdays):
        wk = d.isocalendar()[1]
        if prev_week is not None and wk != prev_week:
            col = i + 1  # +1 за столбец имени
            requests.append({
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1,
                        "startRowIndex": 0,
                        "endRowIndex": len(all_rows),
                    },
                    "left": {"style": "SOLID_MEDIUM", "color": {"red": 0.4, "green": 0.4, "blue": 0.4}},
                }
            })
        prev_week = wk

    # Зафиксировать первую строку и первый столбец
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1},
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }
    })

    if requests:
        sh.batch_update({"requests": requests})

    return f"https://docs.google.com/spreadsheets/d/{sh.id}/edit#gid={ws.id}"


# ── Хелперы форматирования ─────────────────────────────────────────────────

def _fmt_row(sheet_id: int, row_idx: int, bg: tuple, bold: bool = False, font_size: int | None = None) -> dict:
    fmt: dict = {
        "backgroundColor": {"red": bg[0], "green": bg[1], "blue": bg[2]},
        "textFormat": {"bold": bold},
    }
    if font_size:
        fmt["textFormat"]["fontSize"] = font_size
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1},
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    }


def _fmt_cell(sheet_id: int, row_idx: int, col_idx: int, bg: tuple) -> dict:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                "startColumnIndex": col_idx, "endColumnIndex": col_idx + 1,
            },
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": bg[0], "green": bg[1], "blue": bg[2]}}},
            "fields": "userEnteredFormat(backgroundColor)",
        }
    }


def _col_width(sheet_id: int, col_idx: int, px: int) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1},
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }

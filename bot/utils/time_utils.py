from __future__ import annotations
from datetime import date, timedelta
import pytz


def get_kyiv_now():
    tz = pytz.timezone("Europe/Kyiv")
    import datetime
    return datetime.datetime.now(tz)


def get_next_order_date(cutoff_hour: int = 17, cutoff_minute: int = 0, working_sats: set[date] | None = None) -> date:
    """
    Возвращает дату, на которую принимаются заказы прямо сейчас.
    working_sats — множество рабочих суббот.
    """
    now = get_kyiv_now()
    today = now.date()
    weekday = today.weekday()  # 0=Пн … 4=Пт, 5=Сб, 6=Вс

    after_cutoff = (now.hour, now.minute) >= (cutoff_hour, cutoff_minute)

    if weekday == 4:  # Пятница
        tomorrow = today + timedelta(days=1)
        if working_sats and tomorrow in working_sats:
            # Рабочая суббота: если успели до 17 — на субботу, иначе — на Пн
            return tomorrow if not after_cutoff else today + timedelta(days=3)
        return today + timedelta(days=3)  # обычная пятница → Пн

    if weekday in (5, 6):  # Сб или Вс → Пн
        days_to_mon = (7 - weekday) % 7 or 7
        return today + timedelta(days=days_to_mon)

    # Пн–Чт
    if after_cutoff:
        next_day = today + timedelta(days=1)
        if next_day.weekday() == 5:
            wsat = working_sats or set()
            return next_day if next_day in wsat else today + timedelta(days=3)
        return next_day
    return today + timedelta(days=1)


def is_cart_locked(order_date: date, cutoff_hour: int = 17, cutoff_minute: int = 0,
                   open_hour: int = 12, working_sats: set[date] | None = None) -> bool:
    """Корзина заблокирована если прошёл дедлайн накануне или ещё не открылась."""
    now = get_kyiv_now()
    today = now.date()
    weekday = today.weekday()

    after_cutoff = (now.hour, now.minute) >= (cutoff_hour, cutoff_minute)
    before_open  = (now.hour, now.minute) <  (open_hour, 0)

    day_before = order_date - timedelta(days=1)

    # Если сегодня уже после дня накануне — точно заблокировано
    if today > day_before:
        return True

    if today == day_before:
        # Пятница перед рабочей субботой: применяем окно 12–17
        if weekday == 4 and working_sats and order_date in working_sats:
            return before_open or after_cutoff
        # Пн–Чт перед следующим рабочим днём
        if weekday < 4:
            return before_open or after_cutoff
        # Пятница перед обычным Пн — без ограничений
        return after_cutoff

    return False


def parse_cutoff(cutoff_str: str) -> tuple[int, int]:
    """'17:00' → (17, 0)"""
    h, m = cutoff_str.split(":")
    return int(h), int(m)


def parse_working_sats(value: str) -> set[date]:
    """'2026-05-09,2026-05-16' → {date(2026,5,9), date(2026,5,16)}"""
    result: set[date] = set()
    for s in value.split(","):
        s = s.strip()
        if s:
            try:
                result.add(date.fromisoformat(s))
            except ValueError:
                pass
    return result


def encode_working_sats(sats: set[date]) -> str:
    return ",".join(sorted(d.isoformat() for d in sats))

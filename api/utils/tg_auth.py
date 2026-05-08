import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, unquote
from fastapi import HTTPException, status

AUTH_DATA_MAX_AGE = 86400  # 24 hours


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """
    Проверяет подпись Telegram WebApp initData и свежесть auth_date.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        parsed = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid init data format")

    received_hash = parsed.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > AUTH_DATA_MAX_AGE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Init data expired")

    if "user" in parsed:
        try:
            parsed["user"] = json.loads(parsed["user"])
        except Exception:
            pass

    return parsed

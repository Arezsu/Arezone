from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

try:
    import bcrypt  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    bcrypt = None


PIN_RE = re.compile(r"^\d{4}$")


def is_valid_pin(pin: str) -> bool:
    return bool(PIN_RE.match(pin or ""))


def hash_secret(secret: str) -> str:
    if bcrypt is not None:
        return bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    salt = os.urandom(16)
    rounds = 240_000
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, rounds)
    return "pbkdf2_sha256${}${}${}".format(
        rounds,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_secret(secret: str, secret_hash: str) -> bool:
    if not secret_hash:
        return False

    if secret_hash.startswith("$2") and bcrypt is not None:
        return bool(bcrypt.checkpw(secret.encode("utf-8"), secret_hash.encode("utf-8")))

    try:
        algo, rounds, salt_b64, digest_b64 = secret_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(digest_b64.encode("ascii"))
        salt = base64.b64decode(salt_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def get_setting(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()

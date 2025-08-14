import json, time, base64, binascii
from urllib.parse import parse_qsl, unquote_plus
from typing import Dict, Any
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

class TgAuthError(Exception): pass

def _parse_init_data(raw: str) -> Dict[str, Any]:
    if not raw: raise TgAuthError("initData missing")
    d: Dict[str, Any] = {}
    for k, v in parse_qsl(raw, keep_blank_values=True):
        d[unquote_plus(k)] = unquote_plus(v)
    return d

def _sorted_pairs_string(items: Dict[str, Any]) -> str:
    return "\n".join(f"{k}={items[k]}" for k in sorted(items.keys()))

def _b64url_to_bytes(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    s = s.replace("-", "+").replace("_", "/")
    return base64.b64decode(s + pad)

def verify_init_data_ed25519(init_data_raw: str, bot_id: str, public_key_hex: str, ttl: int) -> dict:
    data = _parse_init_data(init_data_raw)
    sig_b64 = data.pop("signature", None)
    data.pop("hash", None)
    if not sig_b64: raise TgAuthError("signature missing")

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if auth_date <= 0 or time.time() - auth_date > ttl:
        raise TgAuthError("auth expired")

    dcs = _sorted_pairs_string(data)
    message = f"{bot_id}:WebAppData\n{dcs}".encode("utf-8")
    try:
        signature = _b64url_to_bytes(sig_b64)
        VerifyKey(bytes.fromhex(public_key_hex)).verify(message, signature)
    except (BadSignatureError, binascii.Error, ValueError):
        raise TgAuthError("invalid signature")

    if "user" not in data: raise TgAuthError("user payload missing")
    try:
        user = json.loads(data["user"])
    except Exception:
        raise TgAuthError("user json decode failed")

    return {"user": user, **{k: v for k, v in data.items() if k != "user"}}

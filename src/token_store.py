# src/token_store.py
import json
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

# ------------------------------------------------------------
# Supabase REST config
# ------------------------------------------------------------
def _supabase_cfg(st):
    try:
        sb = st.secrets.get("supabase", {})
        url = (sb.get("url") or "").rstrip("/")
        # For auth endpoints we must use anon_key.
        # For REST table reads/writes, service_role_key works too (but keep least-privileged if possible).
        anon_key = sb.get("anon_key") or ""
        service_key = sb.get("service_role_key") or anon_key
        if not url or not (anon_key or service_key):
            return None
        return {"url": url, "anon_key": anon_key, "service_key": service_key}
    except Exception:
        return None


# ------------------------------------------------------------
# Existing token storage (user_tokens table)
# ------------------------------------------------------------
def supabase_get_token(st, user_id: str, provider: str = "google_calendar"):
    cfg = _supabase_cfg(st)
    if not cfg:
        return None

    q_user = urllib.parse.quote(user_id)
    q_provider = urllib.parse.quote(provider)

    url = f"{cfg['url']}/rest/v1/user_tokens?user_id=eq.{q_user}&provider=eq.{q_provider}&select=token_json"

    req = urllib.request.Request(
        url,
        headers={
            "apikey": cfg["service_key"],
            "Authorization": f"Bearer {cfg['service_key']}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if isinstance(data, list) and len(data) > 0:
            tok = data[0].get("token_json")
            # token_json might already be JSON string
            if isinstance(tok, str):
                try:
                    return json.loads(tok)
                except Exception:
                    return tok
            return tok
        return None
    except Exception:
        return None


def supabase_upsert_token(st, user_id: str, token_json: dict, provider: str = "google_calendar"):
    cfg = _supabase_cfg(st)
    if not cfg:
        return False

    url = f"{cfg['url']}/rest/v1/user_tokens"

    final_token_val = None
    if token_json is not None:
        if isinstance(token_json, dict):
            final_token_val = json.dumps(token_json)
        else:
            final_token_val = token_json

    payload_dict = {"user_id": user_id, "provider": provider, "token_json": final_token_val}
    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey": cfg["service_key"],
            "Authorization": f"Bearer {cfg['service_key']}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


# ------------------------------------------------------------
# NEW: Supabase OTP login (email)
# ------------------------------------------------------------
def supabase_send_otp(st, email: str) -> tuple[bool, str]:
    """
    Sends a 6-digit OTP to email via Supabase Auth.
    Requires supabase.anon_key in secrets.
    """
    cfg = _supabase_cfg(st)
    if not cfg or not cfg.get("anon_key"):
        return False, "Missing Supabase anon_key in secrets."

    email = (email or "").strip().lower()
    if not email:
        return False, "Enter a valid email."

    url = f"{cfg['url']}/auth/v1/otp"
    payload = json.dumps({"email": email, "create_user": True}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey": cfg["anon_key"],
            "Authorization": f"Bearer {cfg['anon_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15):
            return True, "OTP sent. Check your email."
    except Exception as e:
        return False, f"OTP send failed: {str(e)}"


def supabase_verify_otp(st, email: str, otp_code: str) -> tuple[bool, str, dict]:
    """
    Verifies OTP and returns a Supabase session dict.
    """
    cfg = _supabase_cfg(st)
    if not cfg or not cfg.get("anon_key"):
        return False, "Missing Supabase anon_key in secrets.", {}

    email = (email or "").strip().lower()
    otp_code = (otp_code or "").strip()

    if not email or not otp_code:
        return False, "Email and OTP are required.", {}

    url = f"{cfg['url']}/auth/v1/verify"
    payload = json.dumps({"type": "email", "email": email, "token": otp_code}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey": cfg["anon_key"],
            "Authorization": f"Bearer {cfg['anon_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Supabase returns session info including access_token/refresh_token/user
        return True, "Verified.", data if isinstance(data, dict) else {}
    except Exception as e:
        return False, f"OTP verify failed: {str(e)}", {}


# ------------------------------------------------------------
# NEW: App session persistence (sid) stored in user_tokens table
# ------------------------------------------------------------
APP_SESSION_PROVIDER = "app_session_v1"

def create_app_session(st, email: str) -> str:
    """
    Creates a stable session id stored in Supabase user_tokens table:
      user_id = sid
      provider = app_session_v1
      token_json = {"email":..., "created_at":...}
    """
    email = (email or "").strip().lower()
    if not email:
        return ""

    sid = uuid.uuid4().hex[:20]
    token_json = {
        "email": email,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    ok = supabase_upsert_token(st, sid, token_json, provider=APP_SESSION_PROVIDER)
    return sid if ok else ""


def load_app_session(st, sid: str) -> dict:
    """
    Loads {"email":...} from app session sid.
    """
    sid = (sid or "").strip()
    if not sid:
        return {}
    tok = supabase_get_token(st, sid, provider=APP_SESSION_PROVIDER)
    return tok if isinstance(tok, dict) else {}

# src/token_store.py
import json
import urllib.parse
import urllib.request

def _supabase_cfg(st):
    try:
        sb = st.secrets.get("supabase", {})
        url = (sb.get("url") or "").rstrip("/")
        key = sb.get("service_role_key") or sb.get("anon_key")
        if not url or not key:
            return None
        return {"url": url, "key": key}
    except Exception:
        return None

def supabase_get_token(st, user_id: str, provider: str = "google_calendar"):
    cfg = _supabase_cfg(st)
    if not cfg:
        return None

    # URL Encode strict
    q_user = urllib.parse.quote(user_id)
    q_provider = urllib.parse.quote(provider)
    
    # Supabase REST: SELECT * FROM user_tokens WHERE ...
    url = f"{cfg['url']}/rest/v1/user_tokens?user_id=eq.{q_user}&provider=eq.{q_provider}&select=token_json"

    req = urllib.request.Request(
        url,
        headers={
            "apikey": cfg["key"],
            "Authorization": f"Bearer {cfg['key']}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        # Supabase returns a list [ { "token_json": ... } ]
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("token_json")
        return None
    except Exception as e:
        # If it's a 404 or connection error, return None
        return None

def supabase_upsert_token(st, user_id: str, token_json: dict, provider: str = "google_calendar"):
    cfg = _supabase_cfg(st)
    if not cfg:
        return False

    url = f"{cfg['url']}/rest/v1/user_tokens"
    
    # Supabase UPSERT syntax
    # We must stringify token_json because Supabase usually stores JSON types or Text
    # If token_json is None, we are deleting/clearing
    
    final_token_val = None
    if token_json:
        if isinstance(token_json, dict):
            final_token_val = json.dumps(token_json)
        else:
            final_token_val = token_json

    payload_dict = {
        "user_id": user_id,
        "provider": provider,
        "token_json": final_token_val
    }
    
    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey": cfg["key"],
            "Authorization": f"Bearer {cfg['key']}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal", 
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            # 2xx response means success
            return True
    except Exception as e:
        return False
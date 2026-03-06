# src/llm_router.py
"""
LLM Router — single place to control which model does what.

ROUTING TABLE (change models HERE only, never in brain.py):
  - "brain"    → Claude Haiku  (primary: planning, scheduling, chat, vision)
  - "repair"   → Groq Llama    (JSON repair: fast, cheap, stateless)
  - "regen"    → Claude Haiku  (all _regen_* helpers)
  - "fallback" → Groq Llama    (auto-used when Claude is rate-limited)

HOW TO ADD A NEW ROUTE IN THE FUTURE:
  1. Add a new key to ROUTING_TABLE below
  2. In brain.py, call: router.call("your_new_key", system=..., user=...)
  3. Done. No other files change.

HOW TO UPGRADE MODELS:
  Change CLAUDE_MODEL or GROQ_MODEL below. Nothing else needs touching.
"""

from __future__ import annotations
from typing import Any, Optional

import anthropic
from groq import Groq

# ---------------------------------------------------------------------------
# Model constants — change ONLY here to upgrade or swap
# ---------------------------------------------------------------------------
CLAUDE_MODEL = "claude-haiku-4-5-20251001"   # Primary brain
GROQ_MODEL   = "llama-3.3-70b-versatile"      # JSON repair + fallback

# ---------------------------------------------------------------------------
# Routing table — maps task name → provider
# ---------------------------------------------------------------------------
ROUTING_TABLE: dict[str, str] = {
    "brain":    "claude",   # main get_coo_response call
    "repair":   "groq",     # _repair_json_with_llm (fast, cheap, no intelligence needed)
    "regen":    "claude",   # all _regen_* helpers
    "fallback": "groq",     # explicit fallback route
}


class LLMRouter:
    """
    Thin wrapper. Holds both clients. Routes calls by task name.
    Auto-falls back to Groq if Claude is rate-limited on a "brain" or "regen" call.

    Usage:
        router = LLMRouter(anthropic_key, groq_key)
        text = router.call("brain",  system=sys_prompt, user=user_msg)
        text = router.call("repair", system=repair_prompt, user="Fix JSON.")
        text = router.call("brain",  system=sys_prompt, user=user_msg, image_b64=b64str)
    """

    def __init__(self, anthropic_key: str, groq_key: str) -> None:
        self._claude = anthropic.Anthropic(api_key=anthropic_key)
        self._groq   = Groq(api_key=groq_key) if groq_key else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def call(
        self,
        task: str,
        system: str,
        user: str,
        temperature: float = 0.6,
        max_tokens: int = 900,
        image_b64: Optional[str] = None,
    ) -> str:
        """
        Route a call by task name. Returns raw text string.
        On Claude rate-limit: auto-retries with Groq (if groq_key was provided).
        On any other error: re-raises so brain.py can handle it.
        """
        provider = ROUTING_TABLE.get(task, "claude")
        user = (user or " ").strip() or " "  # never empty

        if provider == "claude":
            try:
                return self._call_claude(system, user, temperature, max_tokens, image_b64)
            except Exception as e:
                if self._is_rate_limited(e) and self._groq is not None:
                    # Auto-fallback to Groq on Claude rate-limit
                    return self._call_groq(system, user, temperature, max_tokens)
                raise

        # provider == "groq"
        if self._groq is None:
            # No Groq key? Fall back to Claude for repair/fallback tasks
            return self._call_claude(system, user, temperature, max_tokens)
        return self._call_groq(system, user, temperature, max_tokens)

    # ------------------------------------------------------------------
    # Static helpers (callable without an instance — used by brain.py's
    # _is_rate_limited which doesn't have a router instance at module level)
    # ------------------------------------------------------------------
    @staticmethod
    def is_rate_limited_static(err: Exception) -> bool:
        return LLMRouter._is_rate_limited(err)

    # ------------------------------------------------------------------
    # Private: Claude call
    # ------------------------------------------------------------------
    def _call_claude(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        image_b64: Optional[str] = None,
    ) -> str:
        if image_b64:
            user_content: Any = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": user},
            ]
        else:
            user_content = user

        msg = self._claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
            temperature=temperature,
        )
        return (msg.content[0].text or "").strip()

    # ------------------------------------------------------------------
    # Private: Groq call
    # ------------------------------------------------------------------
    def _call_groq(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        completion = self._groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        return (completion.choices[0].message.content or "").strip()

    # ------------------------------------------------------------------
    # Private: rate-limit detection (both providers)
    # ------------------------------------------------------------------
    @staticmethod
    def _is_rate_limited(err: Exception) -> bool:
        msg = str(err).lower()
        if any(x in msg for x in ("429", "rate limit", "too many requests", "overloaded")):
            return True
        try:
            if isinstance(err, anthropic.RateLimitError):
                return True
            if isinstance(err, anthropic.APIStatusError) and getattr(err, "status_code", 0) == 429:
                return True
        except Exception:
            pass
        return False

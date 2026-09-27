"""Web Push delivery (VAPID). Farmers subscribe on the public page; officers dispatch alerts."""

from __future__ import annotations

import json
import logging

from app.core.config import get_settings

log = logging.getLogger(__name__)


def push_enabled() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key)


def send_push(subscriptions: list[dict], payload_for) -> dict:
    """Send one notification per subscription. `payload_for(sub)` returns the JSON payload (per language).
    Expired subscriptions (404/410) are reported so the caller can delete them."""
    if not push_enabled() or not subscriptions:
        return {"sent": 0, "failed": 0, "expired": []}
    from pywebpush import WebPushException, webpush

    s = get_settings()
    sent, failed, expired = 0, 0, []
    for sub in subscriptions:
        info = {"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}}
        try:
            webpush(
                subscription_info=info,
                data=json.dumps(payload_for(sub), ensure_ascii=False),
                vapid_private_key=s.vapid_private_key,
                vapid_claims={"sub": s.vapid_subject},
                ttl=3600,
                headers={"Urgency": "high"},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                expired.append(sub["endpoint"])
            log.warning("push failed (%s): %s", status, exc)
            failed += 1
        except Exception as exc:  # network down etc.
            log.warning("push failed: %s", exc)
            failed += 1
    return {"sent": sent, "failed": failed, "expired": expired}

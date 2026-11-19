"""Send a signed synthetic payment or WhatsApp event to a local DishCare instance."""

import argparse
import hashlib
import hmac
import json

import httpx

from app.reliability.config import ReliabilitySettings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel", choices=["payments", "whatsapp"])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--event", default="dishcare-demo-event")
    parser.add_argument("--sender", default="12025550100")
    args = parser.parse_args()
    settings = ReliabilitySettings()

    if args.channel == "payments":
        secret = settings.payment_webhook_secret
        payload = {"event_id": args.event, "payment_id": "PAY001"}
    else:
        secret = settings.whatsapp_app_secret
        payload = {"entry": [{"changes": [{"value": {"messages": [{
            "id": args.event, "from": args.sender, "text": {"body": "What is my balance?"},
        }]}}]}]}
    if not secret.get_secret_value():
        raise SystemExit("Set the corresponding webhook signing secret in .env")
    body = json.dumps(payload).encode()
    signature = hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).hexdigest()
    response = httpx.post(
        f"{args.base_url.rstrip('/')}/api/v1/webhooks/{args.channel}", content=body,
        headers={"X-Hub-Signature-256": "sha256=" + signature}, timeout=90,
    )
    print(response.status_code, response.text)


if __name__ == "__main__":
    main()

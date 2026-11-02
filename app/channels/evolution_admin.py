"""Local operator checks. Never prints credentials, phone numbers or QR contents."""

import argparse
import base64
import json
import os
from pathlib import Path

import httpx

from app.channels.evolution_store import EvolutionStore
from app.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "qr"])
    args = parser.parse_args()
    if not settings.evolution_api_key.get_secret_value() or not settings.pilot_db_path:
        parser.error("Evolution pilot configuration missing")
    with httpx.Client(
        base_url=settings.evolution_url,
        headers={"apikey": settings.evolution_api_key.get_secret_value()},
        timeout=25,
        trust_env=False,
    ) as client:
        status = client.get("/instance/connectionState/" + settings.evolution_instance)
        if status.status_code != 200:
            parser.error("Evolution state unavailable")
        connection = status.json().get("instance", {}).get("state", "unknown")
        if args.action == "status":
            print(
                json.dumps(
                    {
                        "instance": settings.evolution_instance,
                        "connection": connection,
                        "send_enabled": settings.evolution_send_enabled,
                        "authorized_testers": len(
                            [n for n in settings.evolution_allowed_numbers.split(",") if n]
                        ),
                        "queue": EvolutionStore(settings.pilot_db_path).counts(),
                    }
                )
            )
            return
        if connection == "open":
            print("WhatsApp already connected")
            return
        result = client.get("/instance/connect/" + settings.evolution_instance)
        if result.status_code != 200:
            parser.error("Pairing unavailable")
        encoded = result.json().get("base64", "")
        if not encoded.startswith("data:image/png;base64,"):
            parser.error("QR not ready; retry shortly")
        image = base64.b64decode(encoded.split(",", 1)[1], validate=True)
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            parser.error("QR format invalid")
        target = Path(".local/evolution-qr.png").resolve()
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(image)
        os.chmod(target, 0o600)
        print(str(target))


if __name__ == "__main__":
    main()

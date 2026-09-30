"""Email the platform administrator when a guardrail blocks a request."""

import os
import smtplib
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "admin_alerts.log"


def _excerpt(text, limit=500):
    value = " ".join((text or "").split())
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


def _smtp_settings():
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    recipient = os.getenv("ADMIN_EMAIL", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip() or user
    port_raw = os.getenv("SMTP_PORT", "587").strip() or "587"
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    ready = bool(host and user and password and recipient and sender)
    return {
        "ready": ready,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "recipient": recipient,
        "sender": sender,
    }


def _write_log(record):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"{record['timestamp']} | {record['endpoint']} | {record['category']} | "
        f"ip={record['remote_addr']} | {record['reason']} | excerpt={record['excerpt']}\n"
    )
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _send_email(settings, record):
    message = EmailMessage()
    message["Subject"] = (
        f"[AI Platform Alert] {record['category']} on {record['endpoint']}"
    )
    message["From"] = settings["sender"]
    message["To"] = settings["recipient"]
    message.set_content(
        "\n".join(
            [
                "A request was blocked by the platform guardrail.",
                "",
                f"Time: {record['timestamp']}",
                f"Endpoint: {record['endpoint']}",
                f"Category: {record['category']}",
                f"Field: {record['field']}",
                f"Reason: {record['reason']}",
                f"Client IP: {record['remote_addr']}",
                "",
                "Excerpt:",
                record["excerpt"] or "(empty)",
            ]
        )
    )
    with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as server:
        server.starttls()
        server.login(settings["user"], settings["password"])
        server.send_message(message)


def notify_admin(*, endpoint, category, reason, field, excerpt, remote_addr):
    """Record the block and email the admin when SMTP is configured."""
    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "endpoint": endpoint,
        "category": category,
        "reason": reason,
        "field": field,
        "excerpt": _excerpt(excerpt),
        "remote_addr": remote_addr or "unknown",
    }
    _write_log(record)
    settings = _smtp_settings()
    if not settings["ready"]:
        print("Admin email is not configured. Alert saved to logs/admin_alerts.log")
        return {"logged": True, "emailed": False}

    def _deliver():
        try:
            _send_email(settings, record)
            print(f"Admin alert emailed to {settings['recipient']}")
        except Exception as exc:
            print(f"Admin email failed: {exc}")

    threading.Thread(target=_deliver, daemon=True).start()
    return {"logged": True, "emailed": True}

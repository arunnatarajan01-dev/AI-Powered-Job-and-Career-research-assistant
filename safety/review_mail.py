"""Email the requester and the approver after approve, reject, or edit."""

from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
import smtplib
import threading

from safety.admin_alert import _smtp_settings

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "review_mail.log"


def _write(record):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"{record['timestamp']} | {record['action']} | {record['role']} | "
        f"to={record['email']} | party={record['party']} | {record['subject']}\n"
    )
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _deliver(settings, recipient, subject, body):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["sender"]
    message["To"] = recipient
    message.set_content(body)
    with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as server:
        server.starttls()
        server.login(settings["user"], settings["password"])
        server.send_message(message)


def notify_parties(parties, subject, body_for):
    """Log and send one message to each distinct requester and approver address."""
    settings = _smtp_settings()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    sent = []
    failed = []
    seen = set()
    for party in parties:
        email = (party.get("email") or "").strip()
        if "@" not in email or email in seen:
            continue
        seen.add(email)
        record = {
            "timestamp": timestamp,
            "action": party.get("action") or "",
            "role": party.get("role") or "",
            "email": email,
            "party": party.get("party") or "",
            "subject": subject,
        }
        _write(record)
        if not settings["ready"]:
            continue
        body = body_for(party)
        try:
            _deliver(settings, email, subject, body)
            sent.append(email)
        except Exception as exc:
            failed.append(f"{email}: {exc}")
            print(f"Review email failed for {email}: {exc}")
    if not settings["ready"]:
        print("Review mail logged. SMTP settings are missing, so it was not sent.")
    return {
        "logged": bool(seen),
        "emailed": bool(sent) and not failed,
        "sent": sent,
        "failed": failed,
        "addresses": [party["email"] for party in parties if "@" in (party.get("email") or "")],
    }

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl

from .reporting import RenderedEmail


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    sender: str
    recipient: str
    username: str | None = None
    password: str | None = None
    use_tls: bool = True


def save_preview(rendered: RenderedEmail, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = rendered.subject.lower().replace(" ", "-").replace("—", "-")
    text_path = output_dir / f"{safe_name}.txt"
    html_path = output_dir / f"{safe_name}.html"
    text_path.write_text(rendered.text, encoding="utf-8")
    html_path.write_text(rendered.html, encoding="utf-8")
    return text_path, html_path


def send_smtp(rendered: RenderedEmail, settings: SMTPSettings) -> None:
    if not settings.host or not settings.sender or not settings.recipient or settings.port <= 0:
        raise ValueError("SMTP configuration is incomplete")

    message = EmailMessage()
    message["Subject"] = rendered.subject
    message["From"] = settings.sender
    message["To"] = settings.recipient
    message.set_content(rendered.text)
    message.add_alternative(rendered.html, subtype="html")

    with smtplib.SMTP(settings.host, settings.port, timeout=30) as smtp:
        if settings.use_tls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.username:
            if settings.password is None:
                raise ValueError("SMTP password is required when username is configured")
            smtp.login(settings.username, settings.password)
        smtp.send_message(message)

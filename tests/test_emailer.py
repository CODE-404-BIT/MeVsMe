from pathlib import Path
import pytest

from betmodel.emailer import SMTPSettings, save_preview, send_smtp
from betmodel.reporting import RenderedEmail


def sample_email():
    return RenderedEmail(subject="Daily Model Picks", text="hello", html="<html>hello</html>")


def test_preview_is_saved_without_email_credentials(tmp_path: Path):
    text_path, html_path = save_preview(sample_email(), tmp_path)
    assert text_path.read_text() == "hello"
    assert "<html>" in html_path.read_text()


def test_smtp_requires_explicit_configuration():
    with pytest.raises(ValueError, match="SMTP"):
        send_smtp(sample_email(), SMTPSettings(host="", port=587, sender="", recipient=""))

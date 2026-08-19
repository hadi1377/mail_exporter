"""Decode and clean RFC 822 message content."""

from datetime import UTC, datetime
from email.header import decode_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import re

from .privacy import Redactor


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")


def decode_header_value(value: str | None) -> str:
    return "".join(
        part.decode(encoding or "utf-8", errors="replace") if isinstance(part, bytes) else part
        for part, encoding in decode_header(value or "")
    )


def header_addresses(value: str | None, redactor: Redactor) -> list[str]:
    return [redactor.address(address) for _, address in getaddresses([decode_header_value(value)]) if address]


def message_date(value: str | None) -> tuple[datetime, str]:
    try:
        date = parsedate_to_datetime(value or "")
        date = date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
        return date, date.isoformat()
    except (TypeError, ValueError, IndexError):
        return datetime.min.replace(tzinfo=UTC), value or ""


def clean_body(message: Message, redactor: Redactor) -> str:
    plain: str | None = None
    html: str | None = None
    for part in message.walk():
        if part.is_multipart() or "attachment" in part.get("Content-Disposition", "").lower():
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/plain" and plain is None:
            plain = text
        elif part.get_content_type() == "text/html" and html is None:
            html = text
    if plain is None and html:
        parser = _TextExtractor()
        parser.feed(html)
        plain = "".join(parser.parts)
    body = re.split(r"(?im)^\s*(?:On .+wrote:|From: .+|-----Original Message-----)\s*$", plain or "", maxsplit=1)[0]
    return redactor.text(re.sub(r"\n{3,}", "\n\n", body).strip())

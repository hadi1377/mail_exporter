"""Typed domain models for mail export."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Account:
    email: str
    password: str


@dataclass(frozen=True)
class ImapServer:
    host: str
    port: int = 993
    security: str = "ssl"


@dataclass
class MailMessage:
    id: str
    in_reply_to: str
    references: list[str]
    date: str
    sort_date: datetime
    sender: str
    recipients: list[str]
    subject: str
    body: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "in_reply_to": self.in_reply_to,
            "date": self.date,
            "from": self.sender,
            "to": self.recipients,
            "subject": self.subject,
            "body": self.body,
        }

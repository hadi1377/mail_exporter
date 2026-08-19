"""IMAP transport and mailbox retrieval."""

from collections.abc import Iterable
from email import message_from_bytes
import imaplib
import re
import ssl
import sys

from .content import clean_body, decode_header_value, header_addresses, message_date
from .discovery import ImapServerDiscovery
from .models import Account, MailMessage
from .privacy import Redactor


class ImapMailbox:
    def __init__(self, discovery: ImapServerDiscovery) -> None:
        self._discovery = discovery

    def fetch(self, account: Account, limit: int | None, redactor: Redactor) -> list[MailMessage]:
        client = self._connect(account)
        try:
            self._select_inbox(client)
            uids = self._message_uids(client)
            selected = uids if limit is None else uids[-limit:]
            messages = [message for uid in selected if (message := self._fetch(client, uid, redactor))]
            print(f"Exported {len(messages)} message(s) from {redactor.address(account.email)}.", file=sys.stderr)
            return messages
        finally:
            try:
                client.logout()
            except imaplib.IMAP4.error:
                pass

    def _connect(self, account: Account) -> imaplib.IMAP4:
        errors: list[str] = []
        context = ssl.create_default_context()
        for server in self._discovery.candidates(account.email):
            try:
                client = imaplib.IMAP4(server.host, server.port) if server.security == "starttls" else imaplib.IMAP4_SSL(server.host, server.port, ssl_context=context)
                if server.security == "starttls":
                    client.starttls(ssl_context=context)
                client.login(account.email, account.password)
                print(f"Connected to {server.host}:{server.port}", file=sys.stderr)
                return client
            except (OSError, ssl.SSLError, imaplib.IMAP4.error) as error:
                errors.append(f"{server.host}:{server.port} ({error})")
        raise ConnectionError("Could not connect or authenticate. Attempted: " + "; ".join(errors))

    @staticmethod
    def _select_inbox(client: imaplib.IMAP4) -> None:
        if client.select("INBOX", readonly=True)[0] != "OK":
            raise RuntimeError("Could not open INBOX")

    @staticmethod
    def _message_uids(client: imaplib.IMAP4) -> list[bytes]:
        status, result = client.uid("search", None, "ALL")
        if status != "OK":
            raise RuntimeError("Could not list INBOX messages")
        return result[0].split() if result and result[0] else []

    @staticmethod
    def _fetch(client: imaplib.IMAP4, uid: bytes, redactor: Redactor) -> MailMessage | None:
        status, response = client.uid("fetch", uid, "(BODY.PEEK[])")
        if status != "OK" or not response or not isinstance(response[0], tuple):
            return None
        message = message_from_bytes(response[0][1])
        message_id = message.get("Message-ID", f"uid:{uid.decode()}")
        date, date_text = message_date(message.get("Date"))
        sender = header_addresses(message.get("From"), redactor)
        return MailMessage(
            id=redactor.text(message_id),
            in_reply_to=redactor.text(message.get("In-Reply-To", "")),
            references=[redactor.text(value) for value in re.findall(r"<[^>]+>", message.get("References", ""))],
            date=date_text,
            sort_date=date,
            sender=sender[0] if sender else "",
            recipients=header_addresses(message.get("To"), redactor),
            subject=redactor.text(decode_header_value(message.get("Subject"))),
            body=clean_body(message, redactor),
        )

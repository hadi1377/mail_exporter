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
            messages: list[MailMessage] = []
            mailboxes = self._mailboxes(client)
            print(f"Using mailboxes: {', '.join(mailboxes)}", file=sys.stderr)
            for mailbox in mailboxes:
                if not self._select_mailbox(client, mailbox):
                    continue
                uids = self._message_uids(client)
                selected = uids if limit is None else uids[-limit:]
                messages.extend(
                    message
                    for uid in selected
                    if (message := self._fetch(client, uid, mailbox, redactor))
                )
            messages.sort(key=lambda message: message.sort_date, reverse=True)
            if limit is not None:
                messages = messages[:limit]
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
    def _select_mailbox(client: imaplib.IMAP4, mailbox: str) -> bool:
        if client.select(mailbox, readonly=True)[0] == "OK":
            return True
        if mailbox == "INBOX":
            raise RuntimeError(f"Could not open mailbox {mailbox}")
        print(f"Skipping unavailable sent mailbox: {mailbox}", file=sys.stderr)
        return False

    @staticmethod
    def _mailboxes(client: imaplib.IMAP4) -> list[str]:
        """Return INBOX plus folders advertised by the server as sent mail."""
        status, response = client.list()
        if status != "OK" or not response:
            return ["INBOX"]
        sent: list[str] = []
        mailbox_names: list[str] = []
        pending_sent_literal = False
        for item in response:
            if not isinstance(item, bytes):
                continue
            line = item.decode("utf-8", errors="replace")
            if pending_sent_literal:
                if line:
                    sent.append(line)
                    mailbox_names.append(line)
                pending_sent_literal = False
                continue
            quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', line)
            # Mailcow returns a quoted hierarchy delimiter but an unquoted mailbox name:
            # (\HasNoChildren \Sent) "/" Sent
            mailbox = quoted[-1].replace('\\"', '"') if len(quoted) >= 2 else line.rsplit(" ", 1)[-1]
            is_sent = "\\sent" in line.lower()
            if is_sent and re.search(r"\{\d+\}$", line):
                pending_sent_literal = True
                continue
            if mailbox and mailbox != "{}":
                mailbox_names.append(mailbox)
            if is_sent and mailbox:
                sent.append(mailbox)
        if not sent:
            conventional_names = {"sent", "send", "sent items", "sent mail", "sent messages"}
            sent = [
                name
                for name in mailbox_names
                if re.split(r"[/.]", name)[-1].casefold() in conventional_names
            ]
        return list(dict.fromkeys(mailbox for mailbox in ["INBOX", *sent] if mailbox))

    @staticmethod
    def _message_uids(client: imaplib.IMAP4) -> list[bytes]:
        status, result = client.uid("search", None, "ALL")
        if status != "OK":
            raise RuntimeError("Could not list INBOX messages")
        return result[0].split() if result and result[0] else []

    @staticmethod
    def _fetch(client: imaplib.IMAP4, uid: bytes, mailbox: str, redactor: Redactor) -> MailMessage | None:
        status, response = client.uid("fetch", uid, "(BODY.PEEK[])")
        if status != "OK" or not response or not isinstance(response[0], tuple):
            return None
        message = message_from_bytes(response[0][1])
        message_id = message.get("Message-ID", f"{mailbox}:uid:{uid.decode()}")
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
            mailbox=mailbox,
        )

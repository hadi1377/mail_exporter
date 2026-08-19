"""List mail messages through IMAP."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from getpass import getpass
import imaplib
import json
import os
import ssl
import sys
from collections.abc import Iterable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

import dns.resolver


@dataclass(frozen=True)
class ImapServer:
    host: str
    port: int = 993
    security: str = "ssl"


KNOWN_PROVIDERS: dict[str, ImapServer] = {
    "gmail.com": ImapServer("imap.gmail.com"), "googlemail.com": ImapServer("imap.gmail.com"),
    "outlook.com": ImapServer("outlook.office365.com"), "hotmail.com": ImapServer("outlook.office365.com"),
    "live.com": ImapServer("outlook.office365.com"), "msn.com": ImapServer("outlook.office365.com"),
    "yahoo.com": ImapServer("imap.mail.yahoo.com"), "ymail.com": ImapServer("imap.mail.yahoo.com"),
    "rocketmail.com": ImapServer("imap.mail.yahoo.com"), "icloud.com": ImapServer("imap.mail.me.com"),
    "me.com": ImapServer("imap.mail.me.com"), "mac.com": ImapServer("imap.mail.me.com"),
    "aol.com": ImapServer("imap.aol.com"), "zoho.com": ImapServer("imap.zoho.com"),
    "fastmail.com": ImapServer("imap.fastmail.com"),
}


def candidate_servers(address: str) -> Iterable[ImapServer]:
    """Discover IMAP endpoints, then fall back to common host conventions."""
    domain = address.rsplit("@", maxsplit=1)[1].lower()
    known = KNOWN_PROVIDERS.get(domain)
    if known:
        yield known
    yield from autoconfig_servers(address)
    yield from srv_servers(domain)
    for host in (f"imap.{domain}", f"mail.{domain}", domain):
        candidate = ImapServer(host)
        if candidate != known:
            yield candidate


def element_name(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", maxsplit=1)[-1]


def child_text(element: ElementTree.Element, name: str) -> str | None:
    for child in element:
        if element_name(child) == name and child.text:
            return child.text.strip()
    return None


def autoconfig_servers(address: str) -> Iterable[ImapServer]:
    """Read a Thunderbird-compatible HTTPS autoconfig file, if published."""
    domain = address.rsplit("@", maxsplit=1)[1].lower()
    query = urlencode({"emailaddress": address})
    urls = (
        f"https://autoconfig.{domain}/mail/config-v1.1.xml?{query}",
        f"https://{domain}/.well-known/autoconfig/mail/config-v1.1.xml?{query}",
    )
    for url in urls:
        try:
            with urlopen(url, timeout=5) as response:  # nosec B310: HTTPS endpoints only
                root = ElementTree.fromstring(response.read())
        except (URLError, OSError, ElementTree.ParseError):
            continue

        for server in root.iter():
            if element_name(server) != "incomingServer" or server.get("type", "").lower() != "imap":
                continue
            host = child_text(server, "hostname")
            port = child_text(server, "port")
            socket_type = (child_text(server, "socketType") or "SSL").upper()
            if not host or not port or not port.isdigit():
                continue
            if socket_type in {"SSL", "SSL/TLS"}:
                yield ImapServer(host, int(port), "ssl")
            elif socket_type == "STARTTLS":
                yield ImapServer(host, int(port), "starttls")
        return


def srv_servers(domain: str) -> Iterable[ImapServer]:
    """Resolve RFC 6186 IMAP service records, which specify host and port."""
    for label, security in (("_imaps._tcp", "ssl"), ("_imap._tcp", "starttls")):
        try:
            records = dns.resolver.resolve(f"{label}.{domain}", "SRV")
        except dns.resolver.DNSException:
            continue
        for record in sorted(records, key=lambda item: (item.priority, -item.weight)):
            host = str(record.target).rstrip(".")
            if host:
                yield ImapServer(host, int(record.port), security)


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    fragments: list[str] = []
    for part, encoding in decode_header(value):
        fragments.append(part.decode(encoding or "utf-8", errors="replace") if isinstance(part, bytes) else part)
    return "".join(fragments)


def connect(address: str, password: str) -> imaplib.IMAP4:
    errors: list[str] = []
    context = ssl.create_default_context()
    for server in candidate_servers(address):
        try:
            if server.security == "starttls":
                client = imaplib.IMAP4(server.host, server.port)
                client.starttls(ssl_context=context)
            else:
                client = imaplib.IMAP4_SSL(server.host, server.port, ssl_context=context)
            client.login(address, password)
            print(f"Connected to {server.host}:{server.port}", file=sys.stderr)
            return client
        except (OSError, ssl.SSLError, imaplib.IMAP4.error) as error:
            errors.append(f"{server.host}:{server.port} ({error})")
    raise ConnectionError("Could not connect or authenticate with a discovered IMAP server. Attempted: " + "; ".join(errors))


def print_messages(client: imaplib.IMAP4, limit: int | None) -> int:
    status, _ = client.select("INBOX", readonly=True)
    if status != "OK":
        raise RuntimeError("Could not open the INBOX")
    status, result = client.uid("search", None, "ALL")
    if status != "OK":
        raise RuntimeError("Could not list messages in the INBOX")
    uids = result[0].split() if result and result[0] else []
    selected = uids if limit is None else uids[-limit:]
    for uid in reversed(selected):
        status, response = client.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])")
        if status != "OK" or not response or not isinstance(response[0], tuple):
            print(f"Could not fetch message UID {uid.decode()}", file=sys.stderr)
            continue
        message = message_from_bytes(response[0][1])
        print(" | ".join((
            f"uid={uid.decode()}", f"date={decode_header_value(message.get('Date'))}",
            f"from={decode_header_value(message.get('From'))}", f"subject={decode_header_value(message.get('Subject'))}",
        )))
    return len(selected)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print recent messages from an IMAP inbox.")
    parser.add_argument("email", nargs="?", help="IMAP account email address")
    parser.add_argument("--password", help="Password or app password. Defaults to MAIL_PASSWORD or a hidden prompt.")
    parser.add_argument("--limit", type=int, default=100, help="Number of newest messages to print (default: 100).")
    parser.add_argument("--all", action="store_true", help="Print every message in the inbox.")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


def accounts_from_environment() -> list[tuple[str, str]]:
    raw_accounts = os.getenv("MAIL_ACCOUNTS_JSON", "[]")
    try:
        accounts = json.loads(raw_accounts)
    except json.JSONDecodeError as error:
        raise ValueError("MAIL_ACCOUNTS_JSON must be a valid JSON array") from error
    if not isinstance(accounts, list):
        raise ValueError("MAIL_ACCOUNTS_JSON must be a JSON array")

    parsed: list[tuple[str, str]] = []
    for index, account in enumerate(accounts, start=1):
        if not isinstance(account, dict):
            raise ValueError(f"Account {index} must be a JSON object")
        email = account.get("email")
        password = account.get("password")
        if not isinstance(email, str) or not isinstance(password, str) or not email or not password:
            raise ValueError(f"Account {index} must contain non-empty email and password strings")
        parsed.append((email, password))
    return parsed


def export_account(email: str, password: str, limit: int | None) -> None:
    print(f"\n=== {email} ===", file=sys.stderr)
    client = connect(email, password)
    try:
        count = print_messages(client, limit)
        print(f"Printed {count} message(s) for {email}.", file=sys.stderr)
    finally:
        try:
            client.logout()
        except imaplib.IMAP4.error:
            pass


def main() -> None:
    args = parse_args()
    limit = None if args.all else args.limit
    if args.email:
        password = args.password or os.getenv("MAIL_PASSWORD") or getpass("IMAP password: ")
        export_account(args.email, password, limit)
        return

    try:
        accounts = accounts_from_environment()
    except ValueError as error:
        raise SystemExit(f"Error: {error}") from error
    if not accounts:
        raise SystemExit(
            "Error: provide an email address or add at least one account to MAIL_ACCOUNTS_JSON in .env"
        )
    for email, password in accounts:
        export_account(email, password, limit)


if __name__ == "__main__":
    main()

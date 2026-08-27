"""Command-line composition root for the mail exporter."""

import argparse
from getpass import getpass
import json
import os
import sys

from .conversations import ConversationBuilder
from .discovery import ImapServerDiscovery
from .mailbox import ImapMailbox
from .models import Account
from .privacy import Redactor
from .writer import JsonExportWriter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export IMAP inboxes as threaded JSON conversations.")
    parser.add_argument("email", nargs="?", help="IMAP account email address")
    parser.add_argument("--password", help="Password or app password; defaults to MAIL_PASSWORD or a hidden prompt.")
    parser.add_argument("--limit", type=int, help="Export only this many newest messages per account.")
    parser.add_argument("--all", action="store_true", help="Export every message (the default).")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


def configured_accounts() -> list[Account]:
    try:
        raw_accounts = json.loads(os.getenv("MAIL_ACCOUNTS_JSON", "[]"))
    except json.JSONDecodeError as error:
        raise ValueError("MAIL_ACCOUNTS_JSON must be a valid JSON array") from error
    if not isinstance(raw_accounts, list):
        raise ValueError("MAIL_ACCOUNTS_JSON must be a JSON array")
    accounts: list[Account] = []
    for item in raw_accounts:
        if not isinstance(item, dict) or not isinstance(item.get("email"), str) or not isinstance(item.get("password"), str):
            raise ValueError("Each account needs non-empty email and password strings")
        if not item["email"] or not item["password"]:
            raise ValueError("Each account needs non-empty email and password strings")
        accounts.append(Account(item["email"], item["password"]))
    return accounts


def main() -> None:
    args = parse_args()
    try:
        accounts = [Account(args.email, args.password or os.getenv("MAIL_PASSWORD") or getpass("IMAP password: "))] if args.email else configured_accounts()
    except ValueError as error:
        raise SystemExit(f"Error: {error}") from error
    if not accounts:
        raise SystemExit("Error: provide an email address or configure MAIL_ACCOUNTS_JSON")

    redactor = Redactor((account.email for account in accounts), os.getenv("SECURE", "false").lower() in {"1", "true", "yes", "on"})
    keep_html = os.getenv("KEEP_HTML", "false").lower() in {"1", "true", "yes", "on"}
    mailbox = ImapMailbox(ImapServerDiscovery(), keep_html)
    builder = ConversationBuilder()
    exported = []
    for account in accounts:
        messages = mailbox.fetch(account, None if args.all else args.limit, redactor)
        conversations = builder.build(messages, redactor)
        exported.append({"account": redactor.address(account.email), "conversations": conversations})
        print(f"Built {len(conversations)} conversation(s).", file=sys.stderr)
    destination = JsonExportWriter().write(exported)
    print(f"Wrote {destination}", file=sys.stderr)


if __name__ == "__main__":
    main()

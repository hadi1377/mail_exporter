"""IMAP endpoint discovery strategies."""

from collections.abc import Iterable
import ssl
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

import dns.resolver

from .models import ImapServer


KNOWN_PROVIDERS = {
    "gmail.com": ImapServer("imap.gmail.com"), "googlemail.com": ImapServer("imap.gmail.com"),
    "outlook.com": ImapServer("outlook.office365.com"), "hotmail.com": ImapServer("outlook.office365.com"),
    "live.com": ImapServer("outlook.office365.com"), "msn.com": ImapServer("outlook.office365.com"),
    "yahoo.com": ImapServer("imap.mail.yahoo.com"), "ymail.com": ImapServer("imap.mail.yahoo.com"),
    "rocketmail.com": ImapServer("imap.mail.yahoo.com"), "icloud.com": ImapServer("imap.mail.me.com"),
    "me.com": ImapServer("imap.mail.me.com"), "mac.com": ImapServer("imap.mail.me.com"),
    "aol.com": ImapServer("imap.aol.com"), "zoho.com": ImapServer("imap.zoho.com"),
    "fastmail.com": ImapServer("imap.fastmail.com"),
}


class ImapServerDiscovery:
    def candidates(self, address: str) -> Iterable[ImapServer]:
        domain = address.rsplit("@", 1)[1].lower()
        known = KNOWN_PROVIDERS.get(domain)
        if known:
            yield known
        yield from self._autoconfig(address)
        yield from self._srv(domain)
        for host in (f"imap.{domain}", f"mail.{domain}", domain):
            server = ImapServer(host)
            if server != known:
                yield server

    def _autoconfig(self, address: str) -> Iterable[ImapServer]:
        domain = address.rsplit("@", 1)[1].lower()
        query = urlencode({"emailaddress": address})
        for url in (f"https://autoconfig.{domain}/mail/config-v1.1.xml?{query}", f"https://{domain}/.well-known/autoconfig/mail/config-v1.1.xml?{query}"):
            try:
                with urlopen(url, timeout=5, context=ssl.create_default_context()) as response:  # nosec B310: HTTPS only
                    root = ElementTree.fromstring(response.read())
            except (URLError, OSError, ElementTree.ParseError):
                continue
            for node in root.iter():
                if self._name(node) != "incomingServer" or node.get("type", "").lower() != "imap":
                    continue
                host, port = self._child(node, "hostname"), self._child(node, "port")
                security = (self._child(node, "socketType") or "SSL").upper()
                if host and port and port.isdigit() and security in {"SSL", "SSL/TLS", "STARTTLS"}:
                    yield ImapServer(host, int(port), "starttls" if security == "STARTTLS" else "ssl")
            return

    def _srv(self, domain: str) -> Iterable[ImapServer]:
        for label, security in (("_imaps._tcp", "ssl"), ("_imap._tcp", "starttls")):
            try:
                records = dns.resolver.resolve(f"{label}.{domain}", "SRV")
            except dns.resolver.DNSException:
                continue
            for record in sorted(records, key=lambda item: (item.priority, -item.weight)):
                host = str(record.target).rstrip(".")
                if host:
                    yield ImapServer(host, int(record.port), security)

    @staticmethod
    def _name(element: ElementTree.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    def _child(self, element: ElementTree.Element, name: str) -> str | None:
        return next((child.text.strip() for child in element if self._name(child) == name and child.text), None)

"""Privacy transformations for generated exports."""

import re
from collections.abc import Iterable


EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")


class Redactor:
    """Replaces account identities and external addresses deterministically."""

    def __init__(self, owners: Iterable[str], enabled: bool) -> None:
        self._owners = {address.lower() for address in owners}
        self._enabled = enabled
        self._labels: dict[str, str] = {}

    def address(self, value: str) -> str:
        value = value.strip()
        if not self._enabled:
            return value
        if value.lower() in self._owners:
            return "owner@example.com"
        if value:
            return self._labels.setdefault(value.lower(), str(len(self._labels) + 1))
        return ""

    def text(self, value: str) -> str:
        if not self._enabled:
            return value
        return EMAIL_PATTERN.sub(lambda match: self.address(match.group()), value)

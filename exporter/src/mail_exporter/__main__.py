"""Entrypoint for the mail exporter scaffold."""

from datetime import UTC, datetime
import json
from pathlib import Path


def main() -> None:
    output_directory = Path("/output")
    output_directory.mkdir(parents=True, exist_ok=True)

    exported_at = datetime.now(UTC).isoformat()
    destination = output_directory / "mail-export.json"
    destination.write_text(
        json.dumps(
            {
                "status": "scaffold",
                "exported_at": exported_at,
                "message": "Mail provider integration has not been configured yet.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote scaffold export to {destination}")


if __name__ == "__main__":
    main()

# Mail exporter

This application runs entirely in Docker. Its current command is a safe scaffold:
it creates a timestamped JSON export record in `/output` so the container and
host-volume workflow can be verified before a mail-provider integration is added.

Run from the repository root after copying `.env.example` to `.env`:

```sh
docker compose up --build
```

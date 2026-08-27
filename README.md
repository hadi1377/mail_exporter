# Mail exporter

The project runs entirely in Docker—no local Python installation is required. It discovers custom mail servers from Thunderbird-compatible HTTPS autoconfig files and IMAP DNS SRV records, which provide the exact hostname and port (for example, `server.example.com`). It also recognises common public providers and finally tries standard host names for domains that publish no discovery records.

Copy the Compose selection once:

```sh
cp .env.example .env
```

For multiple accounts, edit `.env` with a JSON array (the real `.env` is ignored by Git):

```dotenv
MAIL_ACCOUNTS_JSON='[{"email":"first@example.com","password":"app-password-1"},{"email":"second@example.com","password":"app-password-2"}]'
```

Then run every configured account:

```sh
docker compose run --rm exporter
```

The exporter reads both `INBOX` and any IMAP folder advertised with the `\\Sent` flag. It writes `output/conversations.json`: an array of accounts whose conversations are sorted by newest activity and whose messages are sorted oldest to newest. Each message includes its source `mailbox` and a cleaned `body`. HTML tags are stripped by default so bodies are plain text. Set `KEEP_HTML=true` in `.env` to keep HTML instead. Quoted history in replies is not duplicated. Sanitize `body` before rendering it in a browser.

Set `SECURE=true` in `.env` to anonymize all configured account addresses as `owner@example.com` and every other email address as a stable number. This masking also applies to message bodies, subjects, and message IDs in the JSON export.

Export every available Inbox and Sent message for one account. Docker keeps the password prompt hidden:

```sh
docker compose run --rm exporter you@example.com
```

For a smaller test export, add `--limit 100`.

Alternatively pass an app password through an environment variable:

```sh
MAIL_PASSWORD='your-app-password' docker compose run --rm -e MAIL_PASSWORD exporter you@example.com
```

Use an app password for providers that require multi-factor authentication. For Gmail, IMAP must be enabled and an app password is normally required. The command prints message UID, date, sender, and subject; it does not mark mail as read. To print every message, add `--all`.

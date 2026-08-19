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

List the latest 100 inbox messages. Docker keeps the password prompt hidden:

```sh
docker compose run --rm exporter you@example.com
```

Alternatively pass an app password through an environment variable:

```sh
MAIL_PASSWORD='your-app-password' docker compose run --rm -e MAIL_PASSWORD exporter you@example.com
```

Use an app password for providers that require multi-factor authentication. For Gmail, IMAP must be enabled and an app password is normally required. The command prints message UID, date, sender, and subject; it does not mark mail as read. To print every message, add `--all`.

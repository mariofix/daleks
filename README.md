# daleks
Private mailer to exterminate email queues

A lightweight FastAPI service that accepts email payloads via HTTP and delivers
them asynchronously through one or more SMTP relays.

## Features

- **Fast ingest** — HTTP `POST /api/v1/email` returns `202 Accepted` immediately
- **In-memory queuing** — per-SMTP `asyncio.Queue`, no database required
- **Multiple SMTP accounts** — round-robin or explicit targeting
- **IP / network allow-listing** — requests from unlisted IPs are rejected with 403
- **No auth, no data storage** — only simple log lines
- **Minimal dependencies** — FastAPI + uvicorn + aiosmtplib

## Quick start

```bash
pip install "daleks @ ."

# Copy and edit the example configuration
cp config.example.toml config.toml

# Run the server
daleks
# or: uvicorn daleks.app:app --reload
```

The server listens on `http://0.0.0.0:8000` by default.

## Configuration

Set `DALEKS_CONFIG` to point at your TOML file, or place `config.toml` in
the working directory.  See [`config.example.toml`](config.example.toml) for
all options:

| Key | Default | Description |
|---|---|---|
| `allowed_networks` | `["127.0.0.1/32", "::1/128"]` | CIDR list of allowed client IPs |
| `queue_max_size` | `1000` | Max queued messages per SMTP account (0 = unlimited) |
| `log_level` | `"INFO"` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `[[smtp_accounts]]` | — | One or more SMTP relay definitions (see below) |

Each `[[smtp_accounts]]` entry supports:

| Key | Default | Description |
|---|---|---|
| `name` | required | Unique identifier for this relay |
| `host` | required | SMTP server hostname |
| `port` | `587` | SMTP server port |
| `username` | `""` | SMTP username (empty = no auth) |
| `password` | `""` | SMTP password |
| `use_tls` | `true` | Enable STARTTLS (port 587) |
| `use_ssl` | `false` | Enable implicit TLS (port 465, mutually exclusive with `use_tls`) |
| `timeout` | `30` | Connection timeout in seconds |
| `workers` | `2` | Number of parallel sender coroutines |

## API

### `POST /api/v1/email`

Submit an email for delivery.

```json
{
  "from_address": "noreply@example.com",
  "to": ["recipient@example.com"],
  "subject": "Hello",
  "text_body": "Plain text body",
  "html_body": "<b>HTML body</b>",
  "cc": ["cc@example.com"],
  "reply_to": "reply@example.com",
  "smtp_account": "primary"
}
```

- `to` — string or list of strings  
- `text_body` and/or `html_body` — at least one is required  
- `smtp_account` — optional; omit to use round-robin across all configured accounts  

Returns `202 Accepted` on success, or `429 Too Many Requests` if the queue is full.

### `GET /health`

```json
{ "status": "ok", "queues": { "primary": 3, "secondary": 0 } }
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

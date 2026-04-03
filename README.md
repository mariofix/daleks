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
- **Flexible install** — zero mandatory dependencies; server stack (FastAPI, uvicorn, aiosmtplib) is an optional `[server]` extra

## Installation

Daleks is not published on PyPI. Install it directly from GitHub:

```bash
# Run the server (FastAPI + uvicorn + aiosmtplib included)
pip install "daleks[server] @ git+https://github.com/mariofix/daleks.git"

# Sync HTTP client only (no server stack required)
pip install "daleks[contrib] @ git+https://github.com/mariofix/daleks.git"

# Both server and contrib extras
pip install "daleks[server,contrib] @ git+https://github.com/mariofix/daleks.git"

# Specific tag / release
pip install "daleks[server] @ git+https://github.com/mariofix/daleks.git@v0.1.0"
```

### Install matrix

| Use-case | Command |
|---|---|
| Run the Daleks server | `pip install "daleks[server] @ git+https://github.com/mariofix/daleks.git"` |
| Sync HTTP client only | `pip install "daleks[contrib] @ git+https://github.com/mariofix/daleks.git"` |
| Server + client helpers | `pip install "daleks[server,contrib] @ git+https://github.com/mariofix/daleks.git"` |

Or in `requirements.txt` / `pyproject.toml`:

```
# requirements.txt — server use-case
daleks[server] @ git+https://github.com/mariofix/daleks.git
```

```toml
# pyproject.toml
dependencies = [
    "daleks[server] @ git+https://github.com/mariofix/daleks.git",
]
```

## Quick start

```bash
pip install "daleks[server] @ git+https://github.com/mariofix/daleks.git"

# For local development, clone first and then:
pip install -e ".[server]"

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

```bash
curl -X POST http://localhost:8000/api/v1/email \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "noreply@example.com",
    "to": ["recipient@example.com"],
    "subject": "Hello",
    "text_body": "Plain text body",
    "html_body": "<b>HTML body</b>",
    "smtp_account": "primary"
  }'
```

Request body fields:

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

## Deployment (systemd)

A ready-to-use systemd unit file is included at
[`daleks.service`](daleks.service).  It assumes the package is installed
inside a virtualenv under `/home/zvn/public_apps/daleks/.venv` and that your
configuration file lives at `/home/zvn/public_apps/daleks/config.toml`.

### Install the service

```bash
# 1. Create the install directory and virtualenv
mkdir -p /home/zvn/public_apps/daleks
cd /home/zvn/public_apps/daleks
python3 -m venv .venv
.venv/bin/pip install "daleks[server] @ git+https://github.com/mariofix/daleks.git"

# 2. Copy and edit the configuration
cp config.example.toml config.toml
$EDITOR config.toml

# 3. Install the unit file
sudo cp daleks.service /etc/systemd/system/daleks.service
sudo systemctl daemon-reload

# 4. Enable and start the service
sudo systemctl enable --now daleks
```

### Manage the service

```bash
sudo systemctl status daleks    # check current status
sudo systemctl restart daleks   # restart after a config change
sudo systemctl stop daleks      # stop the service
sudo systemctl disable daleks   # prevent start on boot
```

### View logs with journalctl

All output is routed to the systemd journal — no log files are created.

```bash
# Follow live log output (like tail -f)
journalctl -u daleks -f

# Show all logs for the current boot
journalctl -u daleks -b

# Show the last 100 lines
journalctl -u daleks -n 100

# Show logs since a specific time
journalctl -u daleks --since "2024-01-01 00:00:00"
journalctl -u daleks --since "1 hour ago"

# Show only error-level messages
journalctl -u daleks -p err

# Show logs between two timestamps
journalctl -u daleks --since "2024-01-01 08:00" --until "2024-01-01 09:00"

# Output in JSON format (useful for log shipping)
journalctl -u daleks -o json

# Combine with grep for keyword filtering
journalctl -u daleks | grep "smtp"
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Contrib integrations

The `daleks/contrib/` sub-package contains optional helper modules for common
frameworks.  They require the **`contrib`** optional extra (which adds
`requests`):

```bash
pip install "daleks[contrib] @ git+https://github.com/mariofix/daleks.git"
```

### `daleks.contrib.client` — synchronous HTTP client

A thin wrapper around `requests` for submitting emails to the Daleks API from
any Python application:

```python
from daleks.contrib.client import DaleksClient

with DaleksClient("http://localhost:8000") as client:
    client.send_email(
        from_address="noreply@example.com",
        to=["user@example.com"],
        subject="Hello",
        text_body="Plain body",
        html_body="<b>HTML body</b>",  # optional
    )
```

Constructor parameters:

| Parameter | Default | Description |
|---|---|---|
| `base_url` | required | Base URL of the Daleks server |
| `timeout` | `10` | HTTP request timeout in seconds |
| `smtp_account` | `None` | Default SMTP account name (round-robin if omitted) |

### `daleks.contrib.flask_security_mail` — Flask-Security mail util

`DaleksMailUtil` is a drop-in `mail_util_cls` for
[Flask-Security](https://flask-security-too.readthedocs.io/) that routes all
outgoing security emails (confirmation, password reset, etc.) through the
Daleks queue instead of connecting to SMTP directly.

```python
from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore
from daleks.contrib.flask_security_mail import DaleksMailUtil

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret"
app.config["SECURITY_PASSWORD_SALT"] = "salty"

# Point Flask-Security at the Daleks server
app.config["DALEKS_URL"] = "http://localhost:8000"
# app.config["DALEKS_TIMEOUT"] = 10          # optional, default 10 s
# app.config["DALEKS_SMTP_ACCOUNT"] = None   # optional, uses round-robin

security = Security(
    app,
    user_datastore,
    mail_util_cls=DaleksMailUtil,
)
```

Flask configuration keys used by `DaleksMailUtil`:

| Key | Required | Default | Description |
|---|---|---|---|
| `DALEKS_URL` | ✅ | — | Base URL of the running Daleks server |
| `DALEKS_TIMEOUT` | | `10` | HTTP request timeout in seconds |
| `DALEKS_SMTP_ACCOUNT` | | `None` | SMTP account to target (round-robin if absent) |

### `daleks.contrib.django_backend` — Django email backend

`DaleksEmailBackend` is a drop-in replacement for Django's default SMTP email
backend.  Set it as `EMAIL_BACKEND` and all outgoing emails (sent via
`send_mail`, `send_mass_mail`, class-based views, etc.) are routed through the
Daleks queue instead of connecting to SMTP directly.

```python
# settings.py
EMAIL_BACKEND = "daleks.contrib.django_backend.DaleksEmailBackend"
DALEKS_URL = "http://localhost:8000"
# DALEKS_TIMEOUT = 10          # optional, default 10 s
# DALEKS_SMTP_ACCOUNT = None   # optional, uses round-robin
```

Then use Django's standard email API as usual:

```python
from django.core.mail import send_mail

send_mail(
    subject="Hello",
    message="Plain text body",
    from_email="noreply@example.com",
    recipient_list=["user@example.com"],
)
```

HTML emails via `EmailMultiAlternatives` are also supported:

```python
from django.core.mail import EmailMultiAlternatives

email = EmailMultiAlternatives(
    subject="Hello",
    body="Plain text body",
    from_email="noreply@example.com",
    to=["user@example.com"],
)
email.attach_alternative("<b>HTML body</b>", "text/html")
email.send()
```

Django settings keys used by `DaleksEmailBackend`:

| Key | Required | Default | Description |
|---|---|---|---|
| `DALEKS_URL` | ✅ | — | Base URL of the running Daleks server |
| `DALEKS_TIMEOUT` | | `10` | HTTP request timeout in seconds |
| `DALEKS_SMTP_ACCOUNT` | | `None` | SMTP account to target (round-robin if absent) |

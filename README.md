# deepagents-logs

Provider-agnostic logging for Deep Agents CLI, plus optional one-command setup for
a logged GigaChat provider.

## What it does

This package has two independent layers:

1. **Logging core** — hooks into Deep Agents CLI and exports session artifacts.
2. **Optional provider setup** — configures GigaChat for Deep Agents CLI and routes
   provider traffic through a logged adapter.

You can use the logging core without GigaChat.

The logging core:

- hooks into Deep Agents session lifecycle via `~/.deepagents/hooks.json`
- writes local session exports with a layout close to existing S3 LLM logs
- optionally mirrors those exports to S3-compatible storage

The optional GigaChat setup:

- adds a `gigachat_logged` provider to `~/.deepagents/config.toml`
- can set `gigachat_logged:GigaChat-2-Max` as the Deep Agents default model
- preserves your existing `~/.deepagents/.env` values
- logs GigaChat request/response pairs alongside the Deep Agents session export

## Key layout

```text
<prefix>/<YYYY-MM>-<username>/<session-id>/<filename>
```

Typical files:

```text
README.md
session-meta.json
hook-events.jsonl
2026-04-15T09-02-11.123Z_ab12cd34_request.json
2026-04-15T09-02-11.123Z_ab12cd34_response.json
```


## Install from GitHub

Install `deepagents-logs` as a standalone helper tool first:

```bash
uv tool install "deepagents-logs @ git+https://github.com/trashchenkov/deepagents-logs.git"
```

Then let it install/configure Deep Agents CLI. For logging only:

```bash
deepagents-logs setup \
  --provider none \
  --package-spec "deepagents-logs @ git+https://github.com/trashchenkov/deepagents-logs.git"
```

For logging plus the optional logged GigaChat provider:

```bash
deepagents-logs setup \
  --provider gigachat \
  --package-spec "deepagents-logs @ git+https://github.com/trashchenkov/deepagents-logs.git"
```

Why `--package-spec` is needed: the setup command installs `deepagents-cli` as a
separate `uv tool` environment and must also install `deepagents-logs` into that
Deep Agents environment so hooks and provider imports work at runtime.

## Run Deep Agents normally

After setup, use Deep Agents CLI the usual way. `deepagents-logs` stays in the
background through `~/.deepagents/hooks.json` and the optional logged provider.

```bash
# interactive session
deepagents

# one-shot non-interactive task
deepagents -n "Reply with exactly: OK" -q --no-stream
```

Logs are written locally under `~/.deepagents/log-export/` and, if S3 is enabled,
mirrored to the configured bucket/prefix.

## Setup examples

After installing the package, use `deepagents-logs`. From a source checkout,
replace `deepagents-logs` with `PYTHONPATH=src python -m deepagents_logs.cli`.

```bash
# logging core only: no provider config is changed
deepagents-logs setup --provider none

# logging core + logged GigaChat provider
deepagents-logs setup --provider gigachat

# later add the logged GigaChat provider
deepagents-logs provider gigachat

# later remove only the managed GigaChat provider block
deepagents-logs provider none

# inspect installation state
deepagents-logs status
deepagents-logs doctor
```

For source checkout usage before installing the script entry point:

```bash
PYTHONPATH=src python -m deepagents_logs.cli setup --provider none
PYTHONPATH=src python -m deepagents_logs.cli status
```

## Runtime config

Logging config is stored in:

```text
~/.config/deepagents-logs.env
```

Deep Agents config remains in:

```text
~/.deepagents/config.toml
~/.deepagents/.env
~/.deepagents/hooks.json
```

`~/.deepagents/.env` is where GigaChat credentials belong, for example:

```text
GIGACHAT_CREDENTIALS=...
GIGACHAT_SCOPE=GIGACHAT_API_CORP
GIGACHAT_VERIFY_SSL_CERTS=true
```

Existing values are preserved by setup commands.

## S3 mirror

S3 upload is optional and disabled by default:

```bash
deepagents-logs s3 on
```

Configure S3-compatible storage in `~/.config/deepagents-logs.env`:

```text
DEEPAGENTS_LOGS_S3_ENABLED=1
DEEPAGENTS_LOGS_S3_BUCKET=...
DEEPAGENTS_LOGS_S3_PREFIX=...
DEEPAGENTS_LOGS_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_ENDPOINT_URL=...
```

Variables:

| Variable | Meaning |
| --- | --- |
| `DEEPAGENTS_LOGS_S3_ENABLED` | Enables S3 upload when set to `1`, `true`, `yes`, or `on`. |
| `DEEPAGENTS_LOGS_S3_BUCKET` | Target bucket name. Use a dedicated bucket for Deep Agents logs if possible. |
| `DEEPAGENTS_LOGS_S3_PREFIX` | Optional key prefix inside the bucket, for example `deepagents-logs` or `dev/deepagents-logs`. |
| `DEEPAGENTS_LOGS_S3_REGION` | Region used for AWS SigV4 signing, for example `us-east-1` or `ru-central-1`. |
| `AWS_ACCESS_KEY_ID` | S3 access key ID. |
| `AWS_SECRET_ACCESS_KEY` | S3 secret access key. |
| `AWS_ENDPOINT_URL` | S3-compatible endpoint, for example `https://s3.amazonaws.com`, `https://s3.cloud.ru`, or another provider endpoint. |

Example for an S3-compatible provider:

```text
DEEPAGENTS_LOGS_S3_ENABLED=1
DEEPAGENTS_LOGS_S3_BUCKET=bucket-deepagents-logs
DEEPAGENTS_LOGS_S3_PREFIX=deepagents-logs
DEEPAGENTS_LOGS_S3_REGION=ru-central-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_ENDPOINT_URL=https://s3.cloud.ru
```

Verify configuration:

```bash
deepagents-logs status
deepagents-logs doctor
```

`deepagents-logs status` redacts secret GigaChat values as `present` or
`missing`, but prints non-secret config values directly. For example,
`GIGACHAT_VERIFY_SSL_CERTS=false` is shown as `"false"` rather than `true`;
`true` under the legacy `gigachat_env_present` field means only that a variable
exists.

If S3 is disabled, local logging still works.

## Design notes

- GigaChat support is intentionally optional.
- Provider adapters live under `deepagents_logs.providers`.
- The core hook/session logger should remain provider-agnostic.
- Managed config blocks are bracketed by comments so they can be safely replaced
  or removed without rewriting the user's whole Deep Agents config.

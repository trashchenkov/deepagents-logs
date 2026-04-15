# deepagents-logs

Provider-agnostic logging for Deep Agents CLI, with payload capture moved to the
LangChain chat-model layer instead of a single provider SDK.

## What it does

This package has two independent layers:

1. **Logging core** — hooks into Deep Agents CLI and exports session artifacts.
2. **Optional logged model setup** — installs a `langchain_logged` wrapper that can
   sit in front of any LangChain-compatible Deep Agents model spec.

You can use the logging core without GigaChat.

The logging core:

- hooks into Deep Agents session lifecycle via `~/.deepagents/hooks.json`
- writes local session exports with a layout close to existing S3 LLM logs
- optionally mirrors those exports to S3-compatible storage
- captures lifecycle metadata for any Deep Agents model/provider configuration

The optional logged model setup:

- adds a `langchain_logged` provider to `~/.deepagents/config.toml`
- wraps an inner model spec such as `gigachat:GigaChat-2-Max` or
  `openai:gpt-5.4`
- preserves your existing `~/.deepagents/.env` values
- logs LangChain request/response pairs alongside the Deep Agents session export

Important: full request/response logging still requires Deep Agents to use the
logged wrapper. If Deep Agents keeps using a regular provider directly, this
package will still upload session metadata and hook events, but it will not see
the actual LLM payloads. The recommended path is to switch the default model to
`langchain_logged:<provider:model>`.

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

For logging plus a LangChain-level logged model wrapper around your current Deep
Agents default:

```bash
deepagents-logs setup \
  --provider langchain \
  --package-spec "deepagents-logs @ git+https://github.com/trashchenkov/deepagents-logs.git"
```

For logging plus the optional logged GigaChat convenience setup:

```bash
deepagents-logs setup \
  --provider gigachat \
  --package-spec "deepagents-logs @ git+https://github.com/trashchenkov/deepagents-logs.git"
```

Why `--package-spec` is needed: the setup command installs `deepagents-cli` as a
separate `uv tool` environment and must also install `deepagents-logs` into that
Deep Agents environment so hooks and provider imports work at runtime.

If you already had a Deep Agents model configured manually, run the
`--provider langchain` setup for full payload logging. It wraps your current
default model when possible. If there is no current default, it falls back to a
logged GigaChat default. The managed block now looks like:

```toml
[models]
default = "langchain_logged:gigachat:GigaChat-2-Max"

[models.providers.langchain_logged]
class_path = "deepagents_logs.providers.langchain:LoggedLangChainModel"
models = ["gigachat:GigaChat-2-Max"]
```

If the default remains `gigachat:GigaChat-2-Max`, `openai:gpt-5.4`, or any other
non-logged provider spec, only metadata logs are expected.

## Run Deep Agents normally

After setup, use Deep Agents CLI the usual way. `deepagents-logs` stays in the
background through `~/.deepagents/hooks.json` and the optional logged model
wrapper.

```bash
# interactive session
deepagents

# one-shot non-interactive task
deepagents -n "Reply with exactly: OK" -q --no-stream
```

Logs are written locally under `~/.deepagents/log-export/` and, if S3 is enabled,
mirrored to the configured bucket/prefix.

Expected files:

- With hooks only / non-logged provider: `hook-events.jsonl`, `session-meta.json`
  and sometimes `README.md`.
- With `langchain_logged:<provider:model>`: the same metadata files plus
  `*_request.json` and `*_response.json` LangChain payload logs.

## Setup examples

After installing the package, use `deepagents-logs`. From a source checkout,
replace `deepagents-logs` with `PYTHONPATH=src python -m deepagents_logs.cli`.

```bash
# logging core only: no provider config is changed
deepagents-logs setup --provider none

# logging core + logged wrapper around the current/default model
deepagents-logs setup --provider langchain

# logging core + logged GigaChat convenience setup
deepagents-logs setup --provider gigachat

# later wrap a specific model explicitly
deepagents-logs provider langchain --default-model openai:gpt-5.4

# later add the logged GigaChat convenience wrapper
deepagents-logs provider gigachat

# later remove only the managed logged-provider block
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

`~/.deepagents/.env` is where GigaChat credentials belong when you use the
GigaChat convenience setup, for example:

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
DEEPAGENTS_LOGS_S3_BUCKET=bucket-deepagents-logs
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
| `DEEPAGENTS_LOGS_S3_BUCKET` | Target bucket name. Defaults to `bucket-deepagents-logs` for the team's shared setup; change it if you use another bucket. |
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
- The recommended payload path is `langchain_logged:<provider:model>`.
- Provider adapters live under `deepagents_logs.providers`.
- The core hook/session logger should remain provider-agnostic.
- Managed config blocks are bracketed by comments so they can be safely replaced
  or removed without rewriting the user's whole Deep Agents config.

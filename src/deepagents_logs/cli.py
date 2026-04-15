from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from deepagents_logs.doctor.checks import run_doctor
from deepagents_logs.installers.deepagents_config import (
    configured_default_model,
    install_logged_gigachat_provider,
    install_logged_langchain_provider,
    langchain_logged_provider_installed,
    legacy_logged_gigachat_provider_installed,
    logged_provider_installed,
    normalize_logged_model,
    remove_logged_provider,
)
from deepagents_logs.installers.env_config import install_gigachat_env_template, install_logging_env, set_logging_toggle
from deepagents_logs.installers.hooks_config import install_hook, remove_hook
from deepagents_logs.core.config import load_logging_config
from deepagents_logs.core.env import parse_env_file
from deepagents_logs.core.paths import (
    DEEPAGENTS_CONFIG_PATH,
    DEEPAGENTS_ENV_PATH,
    DEEPAGENTS_HOOKS_PATH,
    DEFAULT_GIGACHAT_MODEL,
    DEFAULT_LOGGED_MODEL,
    LOGGED_GIGACHAT_PROVIDER,
    LOGGED_LANGCHAIN_PROVIDER,
    LOGGING_ENV_PATH,
)


GIGACHAT_SECRET_ENV_KEYS = {
    "GIGACHAT_CREDENTIALS",
    "GIGACHAT_USER",
    "GIGACHAT_PASSWORD",
}
GIGACHAT_STATUS_ENV_KEYS = [
    "GIGACHAT_CREDENTIALS",
    "GIGACHAT_SCOPE",
    "GIGACHAT_USER",
    "GIGACHAT_PASSWORD",
    "GIGACHAT_VERIFY_SSL_CERTS",
    "GIGACHAT_CA_BUNDLE_FILE",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def install_into_deepagents_env(include_gigachat: bool, package_spec: str | None = None) -> None:
    command = [
        "uv",
        "tool",
        "install",
        "deepagents-cli",
        "--reinstall",
    ]
    if package_spec:
        command.extend(["--with", package_spec])
    elif (_repo_root() / "pyproject.toml").exists():
        command.extend(["--with-editable", str(_repo_root())])
    else:
        command.extend(["--with", "deepagents-logs"])
    if include_gigachat:
        command.extend(["--with", "langchain-gigachat"])
    subprocess.run(command, check=True)


def _resolve_default_model(requested: str | None, *, provider: str) -> str:
    if requested:
        if provider == "gigachat":
            return normalize_logged_model(requested, provider_hint="gigachat")
        return normalize_logged_model(requested)
    if provider == "langchain":
        current_default = configured_default_model()
        if current_default and not current_default.startswith(f"{LOGGED_LANGCHAIN_PROVIDER}:"):
            return current_default
        if current_default and current_default.startswith(f"{LOGGED_LANGCHAIN_PROVIDER}:"):
            return current_default.split(":", 1)[1]
        return DEFAULT_LOGGED_MODEL
    return normalize_logged_model(DEFAULT_GIGACHAT_MODEL, provider_hint="gigachat")


def _active_logged_inner_model(default_model: str | None) -> str | None:
    if not default_model:
        return None
    prefix = f"{LOGGED_LANGCHAIN_PROVIDER}:"
    if default_model.startswith(prefix):
        return default_model.removeprefix(prefix)
    return None


def cmd_setup(args: argparse.Namespace) -> int:
    install_logging_env()
    install_hook()
    resolved_model = _resolve_default_model(args.default_model, provider=args.provider)
    if args.provider == "gigachat":
        install_gigachat_env_template()
        install_logged_gigachat_provider(default_model=resolved_model, set_default=not args.no_set_default)
    elif args.provider == "langchain":
        install_logged_langchain_provider(default_model=resolved_model, set_default=not args.no_set_default)
    if args.install_into_deepagents:
        install_into_deepagents_env(
            include_gigachat=args.provider == "gigachat",
            package_spec=args.package_spec,
        )
    print(json.dumps({
        "ok": True,
        "logging_env": str(LOGGING_ENV_PATH),
        "hooks": str(DEEPAGENTS_HOOKS_PATH),
        "config": str(DEEPAGENTS_CONFIG_PATH),
        "provider": args.provider,
        "logged_default_model": resolved_model if args.provider != "none" else None,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    config = load_logging_config()
    deepagents_env = parse_env_file(DEEPAGENTS_ENV_PATH)
    gigachat_env = {
        key: (
            "present"
            if key in GIGACHAT_SECRET_ENV_KEYS and bool(deepagents_env.get(key))
            else "missing"
            if key in GIGACHAT_SECRET_ENV_KEYS
            else deepagents_env.get(key, "")
        )
        for key in GIGACHAT_STATUS_ENV_KEYS
    }
    payload = {
        "logging_env_path": str(LOGGING_ENV_PATH),
        "config_path": str(DEEPAGENTS_CONFIG_PATH),
        "hooks_path": str(DEEPAGENTS_HOOKS_PATH),
        "logging_enabled": config.enabled,
        "local_enabled": config.local_enabled,
        "s3_enabled": config.s3_enabled,
        "local_root": str(config.local_root),
        "bucket": config.bucket,
        "prefix": config.prefix,
        "s3_endpoint": config.endpoint,
        "s3_region": config.region,
        "gigachat_env": gigachat_env,
        "gigachat_env_present": {
            key: bool(deepagents_env.get(key))
            for key in GIGACHAT_STATUS_ENV_KEYS
        },
        "logged_provider_name": LOGGED_LANGCHAIN_PROVIDER,
        "legacy_logged_provider_name": LOGGED_GIGACHAT_PROVIDER,
        "logged_provider_installed": logged_provider_installed(),
        "langchain_logged_provider_installed": langchain_logged_provider_installed(),
        "legacy_logged_gigachat_provider_installed": legacy_logged_gigachat_provider_installed(),
        "logged_gigachat_provider_installed": legacy_logged_gigachat_provider_installed(),
        "deepagents_default_model": configured_default_model(),
        "logged_inner_model": _active_logged_inner_model(configured_default_model()),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_logging(args: argparse.Namespace) -> int:
    set_logging_toggle("DEEPAGENTS_LOGS_ENABLED", args.state == "on")
    print(json.dumps({"ok": True, "logging": args.state}))
    return 0


def cmd_s3(args: argparse.Namespace) -> int:
    set_logging_toggle("DEEPAGENTS_LOGS_S3_ENABLED", args.state == "on")
    print(json.dumps({"ok": True, "s3": args.state}))
    return 0


def cmd_provider(args: argparse.Namespace) -> int:
    resolved_model = _resolve_default_model(args.default_model, provider=args.name)
    if args.name == "gigachat":
        install_gigachat_env_template()
        install_logged_gigachat_provider(default_model=resolved_model, set_default=not args.no_set_default)
    elif args.name == "langchain":
        install_logged_langchain_provider(default_model=resolved_model, set_default=not args.no_set_default)
    elif args.name == "none":
        remove_logged_provider()
    else:
        raise SystemExit(f"Unsupported provider: {args.name}")
    print(json.dumps({
        "ok": True,
        "provider": args.name,
        "logged_default_model": resolved_model if args.name != "none" else None,
    }))
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    if args.state == "on":
        install_hook()
    else:
        remove_hook()
    print(json.dumps({"ok": True, "hook": args.state}))
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    result = run_doctor()
    print(json.dumps({"ok": result.ok, "checks": result.checks}, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deepagents-logs")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup")
    setup.add_argument("--provider", choices=["none", "langchain", "gigachat"], default="none")
    setup.add_argument(
        "--default-model",
        default=None,
        help=(
            "Inner model to wrap with langchain_logged. "
            "Examples: 'openai:gpt-5.4', 'anthropic:claude-sonnet-4-6', or "
            "'GigaChat-2-Max' with --provider gigachat."
        ),
    )
    setup.add_argument(
        "--package-spec",
        default=None,
        help=(
            "Requirement spec used to install deepagents-logs into the Deep Agents CLI tool env. "
            "Use this for GitHub installs, e.g. "
            "'deepagents-logs @ git+https://github.com/owner/deepagents-logs.git'. "
            "Source checkouts default to --with-editable <repo-root>."
        ),
    )
    setup.add_argument("--no-set-default", action="store_true")
    setup.add_argument("--no-install-into-deepagents", dest="install_into_deepagents", action="store_false")
    setup.set_defaults(func=cmd_setup, install_into_deepagents=True)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    logging_cmd = sub.add_parser("logging")
    logging_cmd.add_argument("state", choices=["on", "off"])
    logging_cmd.set_defaults(func=cmd_logging)

    s3 = sub.add_parser("s3")
    s3.add_argument("state", choices=["on", "off"])
    s3.set_defaults(func=cmd_s3)

    provider = sub.add_parser("provider")
    provider.add_argument("name", choices=["none", "langchain", "gigachat"])
    provider.add_argument("--default-model", default=None)
    provider.add_argument("--no-set-default", action="store_true")
    provider.set_defaults(func=cmd_provider)

    hook = sub.add_parser("hook")
    hook.add_argument("state", choices=["on", "off"])
    hook.set_defaults(func=cmd_hook)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))

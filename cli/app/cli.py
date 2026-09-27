import argparse
import asyncio
import getpass
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from app.jira import JiraClient
from app.validator import validate_commit


HOOK_NAME = "commit-msg"
ATLASSIAN_API_TOKEN_URL = (
    "https://id.atlassian.com/manage-profile/security/api-tokens"
)


def get_config_directory() -> Path:
    return Path.home() / ".aist"


def get_config_path() -> Path:
    return get_config_directory() / "config.json"


def load_config() -> dict:
    config_path = get_config_path()

    if not config_path.exists():
        return {}

    try:
        return json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError:
        print(
            f"Invalid AIST configuration file: {config_path}",
            file=sys.stderr,
        )
        return {}


def save_config(config: dict) -> None:
    config_directory = get_config_directory()
    config_directory.mkdir(parents=True, exist_ok=True)

    config_path = get_config_path()
    temp_path = config_path.with_suffix(".tmp")

    temp_path.write_text(
        json.dumps(config, indent=4),
        encoding="utf-8",
    )

    if os.name != "nt":
        temp_path.chmod(0o600)

    temp_path.replace(config_path)


def get_hooks_directory() -> Path:
    """
    Return the global AIST Git hooks directory.
    """

    if os.name == "nt":
        program_data = os.environ.get(
            "PROGRAMDATA",
            r"C:\ProgramData",
        )

        return Path(program_data) / "AIST" / "git-hooks"

    return Path.home() / ".aist" / "git-hooks"


def get_hook_path() -> Path:
    return get_hooks_directory() / HOOK_NAME


def run_git(*args: str) -> subprocess.CompletedProcess:
    """
    Execute a Git command.
    """

    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
    )


def install():
    """
    Install the global Git commit-msg hook.
    """

    hooks_directory = get_hooks_directory()
    hooks_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    hook_path = get_hook_path()

    hook_content = """#!/bin/sh
aistctl validate-commit "$1"
exit $?
"""

    hook_path.write_text(
        hook_content,
        encoding="utf-8",
    )

    if os.name != "nt":
        hook_path.chmod(0o755)

    result = run_git(
        "config",
        "--global",
        "core.hooksPath",
        str(hooks_directory),
    )

    if result.returncode != 0:
        print("Failed to configure Git.")
        print(result.stderr.strip())
        sys.exit(1)

    print("AIST Git Validator installed.")
    print("")
    print(f"Hook directory : {hooks_directory}")
    print(f"Commit hook    : {hook_path}")
    print("")
    print(
        "All Git repositories on this machine now use the"
    )
    print("AIST commit-msg validation hook.")


def uninstall():
    """
    Remove the AIST global commit-msg hook.
    """

    hook_path = get_hook_path()

    if hook_path.exists():
        hook_path.unlink()
        print("AIST Git Validator hook removed.")
    else:
        print("AIST Git Validator hook is not installed.")

    print("")
    print(
        "Note: global Git core.hooksPath was not changed."
    )


def get_token_status(expires_at: str | None) -> str:
    if not expires_at:
        return "expiration date not configured"

    try:
        expiration_date = date.fromisoformat(expires_at)
    except ValueError:
        return "invalid expiration date"

    today = date.today()
    days_remaining = (expiration_date - today).days

    if days_remaining < 0:
        return f"expired {abs(days_remaining)} days ago"

    if days_remaining == 0:
        return "expires today"

    if days_remaining <= 30:
        return f"expires in {days_remaining} days"

    return f"valid for {days_remaining} days"


def configure():
    """
    Configure Jira credentials for the AIST Git Validator.
    """

    existing = load_config()

    print("AIST Git Validator Configuration")
    print("================================")
    print("")

    jira_base_url = input(
        "Jira Base URL"
        + (
            f" [{existing.get('jira_base_url')}]"
            if existing.get("jira_base_url")
            else ""
        )
        + ": "
    ).strip()

    if not jira_base_url:
        jira_base_url = existing.get("jira_base_url", "")

    jira_email = input(
        "Jira Email"
        + (
            f" [{existing.get('jira_email')}]"
            if existing.get("jira_email")
            else ""
        )
        + ": "
    ).strip()

    if not jira_email:
        jira_email = existing.get("jira_email", "")

    print("")
    print("Opening Atlassian API token page...")
    webbrowser.open(ATLASSIAN_API_TOKEN_URL)

    print("")
    print(
        "Create an API token in the browser, then copy and "
        "paste it below."
    )
    print("")

    jira_api_token = getpass.getpass(
        "Jira API Token: "
    ).strip()

    if not jira_api_token:
        jira_api_token = existing.get("jira_api_token", "")

    if not jira_base_url or not jira_email or not jira_api_token:
        print("Jira configuration is incomplete.")
        sys.exit(1)

    expiration_date = input(
        "Token Expiration Date (YYYY-MM-DD): "
    ).strip()

    try:
        expiration = date.fromisoformat(expiration_date)
    except ValueError:
        print(
            "Invalid expiration date. Use YYYY-MM-DD."
        )
        sys.exit(1)

    if expiration < date.today():
        print("Token expiration date cannot be in the past.")
        sys.exit(1)

    print("")
    print("Validating Jira credentials...")

    try:
        jira = JiraClient(
            base_url=jira_base_url,
            email=jira_email,
            api_token=jira_api_token,
        )

        asyncio.run(jira.validate_credentials())

    except Exception as exc:
        print("Unable to validate Jira credentials.")
        print(f"Reason: {exc}")
        sys.exit(1)

    config = {
        "jira_base_url": jira_base_url.rstrip("/"),
        "jira_email": jira_email,
        "jira_api_token": jira_api_token,
        "jira_token_expires": expiration.isoformat(),
    }

    save_config(config)

    print("")
    print("Jira connection successful.")
    print(f"Configuration saved to: {get_config_path()}")


def setup():
    """
    Perform first-time AIST Git Validator setup.
    """

    print("AIST Git Validator Setup")
    print("========================")
    print("")

    configure()

    print("")
    print("Installing Git commit hook...")
    print("")

    install()

    print("")
    print("Setup completed successfully.")


def renew():
    """
    Renew the Jira API token.
    """

    config = load_config()

    if not config:
        print(
            "AIST Git Validator is not configured."
        )
        print("Run: aistctl setup")
        sys.exit(1)

    print("AIST Git Validator Token Renewal")
    print("================================")
    print("")

    print("Opening Atlassian API token page...")
    webbrowser.open(ATLASSIAN_API_TOKEN_URL)

    print("")
    print(
        "Create a new API token in the browser, then "
        "copy and paste it below."
    )
    print("")

    jira_api_token = getpass.getpass(
        "New Jira API Token: "
    ).strip()

    if not jira_api_token:
        print("API token cannot be empty.")
        sys.exit(1)

    expiration_date = input(
        "Token Expiration Date (YYYY-MM-DD): "
    ).strip()

    try:
        expiration = date.fromisoformat(expiration_date)
    except ValueError:
        print(
            "Invalid expiration date. Use YYYY-MM-DD."
        )
        sys.exit(1)

    if expiration < date.today():
        print("Token expiration date cannot be in the past.")
        sys.exit(1)

    print("")
    print("Validating Jira credentials...")

    try:
        jira = JiraClient(
            base_url=config["jira_base_url"],
            email=config["jira_email"],
            api_token=jira_api_token,
        )

        asyncio.run(jira.validate_credentials())

    except Exception as exc:
        print("Unable to validate Jira credentials.")
        print(f"Reason: {exc}")
        sys.exit(1)

    config["jira_api_token"] = jira_api_token
    config["jira_token_expires"] = expiration.isoformat()

    save_config(config)

    print("")
    print("Jira connection successful.")
    print("API token updated successfully.")


def status():
    """
    Display the current installation/configuration status.
    """

    GREEN = "\033[32m"
    RED = "\033[31m"
    RESET = "\033[0m"

    def configured(label, value):
        print(f"{label:<20}: {GREEN}{value}{RESET}")

    def not_configured(label, value):
        print(f"{label:<20}: {RED}{value}{RESET}")

    print("AIST Git Validator")
    print("===================")

    cli_path = shutil.which("aistctl")

    if cli_path:
        configured("CLI", cli_path)
    else:
        not_configured("CLI", "not found")

    git_path = shutil.which("git")

    if git_path:
        configured("Git", git_path)
    else:
        not_configured("Git", "not found")

    hook_path = get_hook_path()

    if hook_path.exists():
        configured("commit-msg hook", hook_path)
    else:
        not_configured(
            "commit-msg hook",
            f"{hook_path} (not installed)",
        )

    result = run_git(
        "config",
        "--global",
        "--get",
        "core.hooksPath",
    )

    if result.returncode == 0:
        configured_path = result.stdout.strip()

        configured(
            "core.hooksPath",
            configured_path,
        )

        if Path(configured_path).resolve() == (
            get_hooks_directory().resolve()
        ):
            configured(
                "AIST hook path",
                "configured",
            )
        else:
            not_configured(
                "AIST hook path",
                "another hooks directory is configured",
            )
    else:
        not_configured(
            "core.hooksPath",
            "not configured",
        )

    config = load_config()

    print("")
    print("Jira configuration")
    print("------------------")

    if config.get("jira_base_url"):
        configured(
            "Jira URL",
            config["jira_base_url"],
        )
    else:
        not_configured(
            "Jira URL",
            "not configured",
        )

    if config.get("jira_email"):
        configured(
            "Jira email",
            config["jira_email"],
        )
    else:
        not_configured(
            "Jira email",
            "not configured",
        )

    if config.get("jira_api_token"):
        configured(
            "Jira API token",
            "configured",
        )
    else:
        not_configured(
            "Jira API token",
            "not configured",
        )

    token_status = get_token_status(
        config.get("jira_token_expires")
    )

    if token_status.startswith(
        ("expired", "expires today", "invalid")
    ):
        not_configured(
            "Token status",
            token_status,
        )
    else:
        configured(
            "Token status",
            token_status,
        )

    if config.get("jira_token_expires"):
        configured(
            "Token expiration",
            config["jira_token_expires"],
        )
    else:
        not_configured(
            "Token expiration",
            "not configured",
        )


async def validate_commit_message(
    message_file: str,
) -> int:
    """
    Validate the commit message supplied by Git.
    """

    message_path = Path(message_file)

    if not message_path.exists():
        print(
            f"Commit message file not found: {message_file}",
            file=sys.stderr,
        )

        return 1

    commit_message = message_path.read_text(
        encoding="utf-8",
    )

    try:
        jira = JiraClient()
    except KeyError:
        print("")
        print("Commit rejected")
        print(
            "AIST Git Validator is not configured."
        )
        print("Run: aistctl setup")
        print("")

        return 1

    result = await validate_commit(
        commit_message,
        jira,
    )

    if result["valid"]:
        print(
            f"Jira validation passed: "
            f"{result['jira_key']}"
        )

        return 0

    print("")
    print("Commit rejected")
    print(f"   {result['reason']}")
    print("")

    return 1


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="aistctl",
        description=(
            "Validate AIST Jira issues in Git "
            "commit messages."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "setup",
        help="Configure Jira and install the Git hook.",
    )

    subparsers.add_parser(
        "configure",
        help="Configure Jira credentials.",
    )

    subparsers.add_parser(
        "renew",
        help="Replace the Jira API token.",
    )

    subparsers.add_parser(
        "install",
        help="Install the global Git commit-msg hook.",
    )

    subparsers.add_parser(
        "uninstall",
        help="Remove the AIST Git commit-msg hook.",
    )

    subparsers.add_parser(
        "status",
        help="Show installation and configuration status.",
    )

    validate_parser = subparsers.add_parser(
        "validate-commit",
        help="Validate a Git commit message.",
    )

    validate_parser.add_argument(
        "message_file",
        help="Path to the Git commit message file.",
    )

    args = parser.parse_args()

    if args.command == "setup":
        setup()
        return

    if args.command == "configure":
        configure()
        return

    if args.command == "renew":
        renew()
        return

    if args.command == "install":
        install()
        return

    if args.command == "uninstall":
        uninstall()
        return

    if args.command == "status":
        status()
        return

    if args.command == "validate-commit":
        exit_code = asyncio.run(
            validate_commit_message(
                args.message_file,
            )
        )

        sys.exit(exit_code)


if __name__ == "__main__":
    main()
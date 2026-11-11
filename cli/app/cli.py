import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

from app.jira import JiraClient
from app.updater import install_update_task, remove_update_task, run_validator, update_validator


HOOK_NAME = "pre-commit"
LEGACY_HOOK_NAME = "commit-msg"
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
    Return the per-user global AIST Git hooks directory.

    The hook is intentionally stored under the current user's profile so
    installation does not require Administrator privileges.
    """

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
    Install the global Git pre-commit hook.
    """

    print_banner()

    hooks_directory = get_hooks_directory()
    hook_path = get_hook_path()

    result = run_git(
        "config",
        "--global",
        "--get",
        "core.hooksPath",
    )

    if (
        hook_path.exists()
        and result.returncode == 0
        and Path(result.stdout.strip()).resolve()
        == hooks_directory.resolve()
    ):
        print("AIST Git pre-commit hook is already installed.")
        print("")
        print(f"Hook directory : {hooks_directory}")
        print(f"Pre-commit hook    : {hook_path}")
        print(f"Git hooks path : {hooks_directory}")
        return

    print("Installing Git pre-commit hook...")
    print("")

    hooks_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    legacy_hook_path = hooks_directory / LEGACY_HOOK_NAME
    if legacy_hook_path.exists():
        legacy_content = legacy_hook_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        if "aistctl validate-commit" in legacy_content:
            legacy_hook_path.unlink()
            print("Previous AIST commit-message hook removed.")

    hook_content = """#!/bin/sh
aistctl validate-storedprocs
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
        print("Unable to configure Git.")
        if result.stderr.strip():
            print(f"Reason: {result.stderr.strip()}")
        sys.exit(1)

    install_update_task()

    print("Git hook installed.")
    print("")
    print("Configuration")
    print("-------------")
    print(f"Hook directory : {hooks_directory}")
    print(f"Pre-commit hook    : {hook_path}")
    print(f"Git hooks path : {hooks_directory}")
    print("")
    print("AISTCTL is ready.")
    print("")
    print(
        "All Git repositories for this user now use "
        "AIST stored procedure validation."
    )

def uninstall():
    """
    Remove the AIST Git integration and local configuration.
    """

    hooks_directory = get_hooks_directory()
    hook_path = get_hook_path()
    legacy_hook_path = hooks_directory / LEGACY_HOOK_NAME
    config_path = get_config_path()

    remove_update_task()

    print("Removing AIST Stored Procedure Validator...")
    print("")

    # Remove the AIST pre-commit hook.
    if hook_path.exists():
        try:
            hook_path.unlink()
            print("Git pre-commit hook removed.")
        except OSError as exc:
            print("Unable to remove the Git pre-commit hook.")
            print(f"Reason: {exc}")
            sys.exit(1)
    else:
        print("Git pre-commit hook not found.")

    if legacy_hook_path.exists():
        try:
            legacy_content = legacy_hook_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if "aistctl validate-commit" in legacy_content:
                legacy_hook_path.unlink()
                print("Previous AIST commit-message hook removed.")
        except OSError as exc:
            print("Unable to remove the previous AIST commit-message hook.")
            print(f"Reason: {exc}")
            sys.exit(1)

    # Only remove core.hooksPath if it currently points to
    # the AIST-managed hook directory.
    result = run_git(
        "config",
        "--global",
        "--get",
        "core.hooksPath",
    )

    configured_hooks_path = result.stdout.strip()

    if configured_hooks_path:
        try:
            configured_path = Path(
                configured_hooks_path
            ).expanduser().resolve()

            expected_path = hooks_directory.resolve()

            if configured_path == expected_path:
                unset_result = run_git(
                    "config",
                    "--global",
                    "--unset",
                    "core.hooksPath",
                )

                if unset_result.returncode == 0:
                    print("Global Git hooks path removed.")
                elif unset_result.returncode == 5:
                    print("Global Git hooks path already removed.")
                else:
                    print(
                        "Unable to remove the global Git hooks path."
                    )
                    if unset_result.stderr.strip():
                        print(
                            f"Reason: "
                            f"{unset_result.stderr.strip()}"
                        )
                    sys.exit(1)

        except OSError:
            pass

    # Remove the AIST configuration.
    if config_path.exists():
        try:
            config_path.unlink()
            print("AIST configuration removed.")
        except OSError as exc:
            print("Unable to remove AIST configuration.")
            print(f"Reason: {exc}")
            sys.exit(1)

    # Remove the AIST hook directory if it is now empty.
    if hooks_directory.exists():
        try:
            hooks_directory.rmdir()
        except OSError:
            pass

    # Remove the AIST configuration directory if it is now empty.
    config_directory = get_config_directory()

    if config_directory.exists():
        try:
            config_directory.rmdir()
        except OSError:
            pass

    print("")
    print("AIST Stored Procedure Validator removed.")


def configure():
    """
    Configure Jira credentials for the AIST Stored Procedure Validator.
    """

    existing = load_config()

    print("AIST Stored Procedure Validator Configuration")
    print("================================")
    print("")
    print("Jira configuration")
    print("------------------")

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

    if not jira_base_url or not jira_email:
        print("")
        print("Jira configuration is incomplete.")
        print("Jira Base URL and Jira Email are required.")
        sys.exit(1)

    print("")
    print("API token")
    print("---------")
    print("Opening Atlassian API token page...")
    webbrowser.open(ATLASSIAN_API_TOKEN_URL)

    print("")
    print(
        "Create an API token in the browser, then copy and "
        "paste it below."
    )
    print("")

    jira_api_token = input(
        "Jira API Token: "
    ).strip()

    if not jira_api_token:
        jira_api_token = existing.get("jira_api_token", "")

    if not jira_api_token:
        print("")
        print("Jira API token is required.")
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
        print("")
        print("Unable to validate Jira credentials.")
        print(f"Reason: {exc}")
        print("")
        print(
            "Check your Jira Base URL, email, and API token "
            "and try again."
        )
        sys.exit(1)

    config = {
        "jira_base_url": jira_base_url.rstrip("/"),
        "jira_email": jira_email,
        "jira_api_token": jira_api_token,
    }

    save_config(config)

    print("")
    print("Jira connection successful.")
    print(f"Configuration saved to: {get_config_path()}")


def setup():
    """
    Perform first-time AIST Stored Procedure Validator setup.
    """

    print("AIST Stored Procedure Validator Setup")
    print("========================")
    print("")
    print(
        "This will configure your Jira connection "
        "and install the Git pre-commit hook."
    )
    print("")

    configure()

    print("")
    print("Git configuration")
    print("-----------------")
    print("Installing Git pre-commit hook...")
    print("")

    try:
        install()
    except Exception as exc:
        print("")
        print("Unable to install the Git pre-commit hook.")
        print(f"Reason: {exc}")
        print("")
        print("Your Jira configuration was saved.")
        print("You can retry the installation with:")
        print("  aistctl install")
        sys.exit(1)

    print("")
    print("Setup completed successfully.")


def renew():
    """
    Renew the Jira API token.
    """

    config = load_config()

    if not config:
        print("AIST Stored Procedure Validator is not configured.")
        print("")
        print("Run:")
        print("  aistctl setup")
        sys.exit(1)

    print("AIST Stored Procedure Validator Token Renewal")
    print("================================")
    print("")
    print(
        "Your existing API token will remain unchanged "
        "until the new token is validated."
    )
    print("")

    print("Opening Atlassian API token page...")
    webbrowser.open(ATLASSIAN_API_TOKEN_URL)

    print("")
    print(
        "Create a new API token in the browser, then "
        "copy and paste it below."
    )
    print("")

    try:
        jira_api_token = input(
            "New Jira API Token: "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print("")
        print("Token renewal cancelled.")
        return

    if not jira_api_token:
        print("")
        print("API token cannot be empty.")
        print("Existing API token was not changed.")
        sys.exit(1)

    print("")
    print("Validating new Jira credentials...")

    try:
        jira = JiraClient(
            base_url=config["jira_base_url"],
            email=config["jira_email"],
            api_token=jira_api_token,
        )

        asyncio.run(jira.validate_credentials())

    except Exception as exc:
        print("")
        print("Unable to validate the new Jira API token.")
        print(f"Reason: {exc}")
        print("")
        print("Existing API token was not changed.")
        sys.exit(1)

    # Only update the existing configuration after the new
    # token has passed all validation.
    config["jira_api_token"] = jira_api_token

    save_config(config)

    print("")
    print("New Jira API token validated successfully.")
    print("API token updated successfully.")

def print_banner():
    print(
        r"""
 █████╗ ██╗███████╗████████╗ ██████╗████████╗██╗     
██╔══██╗██║██╔════╝╚══██╔══╝██╔════╝╚══██╔══╝██║     
███████║██║███████╗   ██║   ██║        ██║   ██║     
██╔══██║██║╚════██║   ██║   ██║        ██║   ██║     
██║  ██║██║███████║   ██║   ╚██████╗   ██║   ███████╗
╚═╝  ╚═╝╚═╝╚══════╝   ╚═╝    ╚═════╝   ╚═╝   ╚══════╝
"""
    )

def status():
    """
    Display the current installation and configuration status.
    """

    GREEN = "\033[32m"
    RED = "\033[31m"
    RESET = "\033[0m"

    def configured(label, value):
        print(f"{label:<20}: {GREEN}{value}{RESET}")

    def not_configured(label, value):
        print(f"{label:<20}: {RED}{value}{RESET}")

    print("AIST Stored Procedure Validator")
    print("===================")

    # CLI
    print("")
    print("CLI")
    print("---")

    cli_path = shutil.which("aistctl")

    if cli_path:
        configured("CLI", cli_path)
    else:
        not_configured("CLI", "not found")

    # Git
    print("")
    print("Git")
    print("---")

    git_path = shutil.which("git")

    if git_path:
        configured("Git", git_path)
    else:
        not_configured("Git", "not found")

    hook_path = get_hook_path()

    if hook_path.exists():
        configured("Pre-commit hook", str(hook_path))
    else:
        not_configured(
            "Pre-commit hook",
            "not installed",
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

    # Jira
    config = load_config()

    print("")
    print("Jira")
    print("----")

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
            "API token",
            "configured",
        )
    else:
        not_configured(
            "API token",
            "not configured",
        )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="aistctl",
        description="AIST Stored Procedure Validator",
        usage="aistctl <command> [flags]",
        epilog='Use "aistctl <command> --help" for more information.',
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="<command>",
        required=True,
    )

    setup_parser = subparsers.add_parser(
        "setup",
        help="Configure Jira and install the Git hook.",
        description="Configure Jira and install the stored procedure validation hook.",
    )
    setup_parser.set_defaults(handler=lambda args: setup())

    configure_parser = subparsers.add_parser(
        "configure",
        help="Configure Jira credentials.",
        description="Configure the Jira connection used by AIST Stored Procedure Validator.",
    )
    configure_parser.set_defaults(handler=lambda args: configure())

    renew_parser = subparsers.add_parser(
        "renew",
        help="Replace the Jira API token.",
        description="Replace the Jira API token without changing other configuration.",
    )
    renew_parser.set_defaults(handler=lambda args: renew())

    install_parser = subparsers.add_parser(
        "install",
        help="Install the global Git pre-commit hook.",
        description="Install the global Git pre-commit hook.",
    )
    install_parser.set_defaults(handler=lambda args: install())

    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Remove the AIST Git pre-commit hook.",
        description="Remove the AIST Git pre-commit hook.",
    )
    uninstall_parser.set_defaults(handler=lambda args: uninstall())

    status_parser = subparsers.add_parser(
        "status",
        help="Show installation and configuration status.",
        description="Show AIST Stored Procedure Validator installation and configuration status.",
    )
    status_parser.set_defaults(handler=lambda args: status())

    update_parser = subparsers.add_parser(
        "update",
        help="Check for and install validator updates.",
        description="Download the latest verified stored procedure validator release.",
    )
    update_parser.add_argument("--quiet", action="store_true", help=argparse.SUPPRESS)
    update_parser.set_defaults(handler=lambda args: update_validator(quiet=args.quiet))

    # Internal command used by the Git pre-commit hook.
    validate_parser = subparsers.add_parser(
        "validate-storedprocs",
        help=argparse.SUPPRESS,
        description=argparse.SUPPRESS,
    )
    validate_parser.set_defaults(
        handler=lambda args: run_validator()
    )

    # Keep the hook entry point available to Git without exposing it
    # as a customer-facing command.
    subparsers._choices_actions = [
        action
        for action in subparsers._choices_actions
        if action.dest != "validate-storedprocs"
    ]

    return parser


def dispatch(args):
    result = args.handler(args)
    if isinstance(result, int):
        sys.exit(result)


def main():
    load_dotenv()

    try:
        parser = build_parser()
        args = parser.parse_args()
        dispatch(args)
    except KeyboardInterrupt:
        print("")
        print("Operation cancelled.")
        sys.exit(1)
    except Exception as exc:
        print("")
        print("AIST Stored Procedure Validator encountered an unexpected error.")
        print(f"Reason: {exc}")
        print("")
        sys.exit(1)


if __name__ == "__main__":
    main()
import argparse
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.jira import JiraClient
from app.validator import validate_commit


HOOK_NAME = "commit-msg"


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

    # Git for Windows executes hooks through its shell.
    hook_content = """#!/bin/sh
aistctl validate-commit "$1"
exit $?
"""

    hook_path.write_text(
        hook_content,
        encoding="utf-8",
    )

    # Required on Linux/macOS.
    if os.name != "nt":
        hook_path.chmod(0o755)

    result = run_git(
        "config",
        "--global",
        "core.hooksPath",
        str(hooks_directory),
    )

    if result.returncode != 0:
        print("❌ Failed to configure Git.")
        print(result.stderr.strip())
        sys.exit(1)

    print("✅ AIST Git Validator installed.")
    print("")
    print(f"Hook directory : {hooks_directory}")
    print(f"Commit hook    : {hook_path}")
    print("")
    print("All Git repositories on this machine now use the")
    print("AIST commit-msg validation hook.")


def uninstall():
    """
    Remove the AIST global commit-msg hook.

    We remove only our hook. We intentionally do not unset
    core.hooksPath automatically because another tool may be
    using the same global setting.
    """

    hook_path = get_hook_path()

    if hook_path.exists():
        hook_path.unlink()
        print("✅ AIST Git Validator hook removed.")
    else:
        print("ℹ️ AIST Git Validator hook is not installed.")

    print("")
    print(
        "Note: global Git core.hooksPath was not changed."
    )

def status():
    """
    Display the current installation/configuration status.
    """

    GREEN = "\033[32m"
    RED = "\033[31m"
    RESET = "\033[0m"

    def configured(label, value):
        print(f"{label:<18}: {GREEN}{value}{RESET}")

    def not_configured(label, value):
        print(f"{label:<18}: {RED}{value}{RESET}")

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

        configured("core.hooksPath", configured_path)

        if Path(configured_path).resolve() == (
            get_hooks_directory().resolve()
        ):
            configured("AIST hook path", "configured")
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

    required_variables = [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
    ]

    print("")
    print("Jira configuration")
    print("------------------")

    for variable in required_variables:
        if os.getenv(variable):
            configured(variable, "configured")
        else:
            not_configured(variable, "not configured")

async def validate_commit_message(
    message_file: str,
) -> int:
    """
    Validate the commit message supplied by Git.
    """

    message_path = Path(message_file)

    if not message_path.exists():
        print(
            f"❌ Commit message file not found: {message_file}",
            file=sys.stderr,
        )

        return 1

    commit_message = message_path.read_text(
        encoding="utf-8",
    )

    jira = JiraClient()

    result = await validate_commit(
        commit_message,
        jira,
    )

    if result["valid"]:
        print(
            f"✓ Jira validation passed: "
            f"{result['jira_key']}"
        )

        return 0

    print("")
    print("❌ Commit rejected")
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

    # install
    subparsers.add_parser(
        "install",
        help="Install the global Git commit-msg hook.",
    )

    # uninstall
    subparsers.add_parser(
        "uninstall",
        help="Remove the AIST Git commit-msg hook.",
    )

    # status
    subparsers.add_parser(
        "status",
        help="Show installation and configuration status.",
    )

    # validate-commit
    validate_parser = subparsers.add_parser(
        "validate-commit",
        help="Validate a Git commit message.",
    )

    validate_parser.add_argument(
        "message_file",
        help="Path to the Git commit message file.",
    )

    args = parser.parse_args()

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
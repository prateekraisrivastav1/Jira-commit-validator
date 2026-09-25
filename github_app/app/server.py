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
    Return the global Git hooks directory used by this validator.
    """

    if os.name == "nt":
        path = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        return path / "AIST" / "git-hooks"

    return Path.home() / ".aist" / "git-hooks"


def get_hook_path() -> Path:
    return get_hooks_directory() / HOOK_NAME


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
    )


def install():
    hooks_dir = get_hooks_directory()
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_path = get_hook_path()

    # The hook calls the installed CLI.
    if os.name == "nt":
        hook_content = """#!/bin/sh
aist-git-validator validate-commit "$1"
exit $?
"""
    else:
        hook_content = """#!/bin/sh
exec aist-git-validator validate-commit "$1"
"""

    hook_path.write_text(
        hook_content,
        encoding="utf-8",
    )

    if os.name != "nt":
        hook_path.chmod(0o755)

    # Configure Git to use our global hooks directory.
    result = run_git(
        "config",
        "--global",
        "core.hooksPath",
        str(hooks_dir),
    )

    if result.returncode != 0:
        print("❌ Failed to configure Git.")
        print(result.stderr.strip())
        sys.exit(1)

    print("✅ AIST Git validator installed.")
    print(f"   Hooks directory: {hooks_dir}")
    print(f"   Hook: {hook_path}")
    print("")
    print("Git commit validation is now enabled.")


def uninstall():
    hook_path = get_hook_path()

    if hook_path.exists():
        hook_path.unlink()
        print(f"Removed: {hook_path}")
    else:
        print("AIST Git hook is not installed.")

    print("")
    print(
        "Note: core.hooksPath was not automatically removed because "
        "it may be used by other Git hooks."
    )


def doctor():
    print("AIST Git Validator")
    print("-------------------")

    # Git
    git_path = shutil.which("git")

    if git_path:
        print(f"✓ Git: {git_path}")
    else:
        print("✗ Git not found")

    # CLI
    cli_path = shutil.which("aist-git-validator")

    if cli_path:
        print(f "CLI: {cli_path}")
    else:
        print("CLI command not found on PATH")

    # Environment
    required_env = [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
    ]

    for variable in required_env:
        if os.getenv(variable):
            print(f"✓ {variable}")
        else:
            print(f"✗ {variable} is not configured")

    # Git hook
    hook_path = get_hook_path()

    if hook_path.exists():
        print(f"✓ Git hook: {hook_path}")
    else:
        print(f"✗ Git hook missing: {hook_path}")

    # Git configuration
    result = run_git(
        "config",
        "--global",
        "--get",
        "core.hooksPath",
    )

    if result.returncode == 0:
        print(f"✓ Git core.hooksPath: {result.stdout.strip()}")
    else:
        print("✗ Git core.hooksPath is not configured")


async def validate_commit(message_file: str) -> int:
    message_path = Path(message_file)

    if not message_path.exists():
        print(
            f"❌ Commit message file does not exist: {message_file}",
            file=sys.stderr,
        )
        return 1

    commit_message = message_path.read_text(
        encoding="utf-8",
    )

    jira = JiraClient()

    result = await validate_commit_message(
        commit_message,
        jira,
    )

    jira_key = result.get("jira_key")

    if result["valid"]:
        print(f"✓ Jira validation passed: {jira_key}")
        print("✓ Commit allowed")
        return 0

    print("")
    print("❌ Commit rejected")
    print(f"   {result['reason']}")
    print("")

    return 1


async def validate_commit_message(
    commit_message: str,
    jira_client: JiraClient,
):
    return await validate_commit(
        commit_message,
        jira_client,
    )


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="aist-git-validator",
        description="Validate AIST Jira issues in Git commit messages.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
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
        "doctor",
        help="Check Git, Jira and hook configuration.",
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

    if args.command == "install":
        install()
        return

    if args.command == "uninstall":
        uninstall()
        return

    if args.command == "doctor":
        doctor()
        return

    if args.command == "validate-commit":
        exit_code = asyncio.run(
            validate_commit(
                args.message_file,
            )
        )
        sys.exit(exit_code)


if __name__ == "__main__":
    main()

import asyncio
import re
import subprocess

from app.jira import (
    JiraClient,
    JiraAuthenticationError,
    JiraConnectionError,
    JiraRateLimitError,
    JiraUnexpectedResponseError,
)


JIRA_PATTERN = re.compile(r"\bAIST-\d+\b", re.IGNORECASE)


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
    )


def get_changed_stored_procedure_files() -> list[str]:
    result = run_git(
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMR",
        "--",
        "snowflake/storedprocs/",
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "Unable to inspect staged Git changes."
        )

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def get_added_lines() -> list[str]:
    result = run_git(
        "diff",
        "--cached",
        "--no-ext-diff",
        "--unified=0",
        "--",
        "snowflake/storedprocs/",
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "Unable to read staged SQL changes."
        )

    added_lines = []

    for line in result.stdout.splitlines():
        if line.startswith("+++") or not line.startswith("+"):
            continue

        added_lines.append(line[1:].strip())

    return added_lines


async def validate_jira_issues(jira_keys: list[str]) -> bool:
    jira = JiraClient()

    await jira.validate_credentials()

    for jira_key in jira_keys:
        exists = await jira.issue_exists(jira_key)

        if not exists:
            print(f"Validation failed: {jira_key} does not exist in Jira.")
            return False

        print(f"Jira issue verified: {jira_key}")

    return True


def validate_stored_procedures() -> int:
    try:
        changed_files = get_changed_stored_procedure_files()

        # Skip validation if no stored procedure files are staged.
        if not changed_files:
            return 0

        added_lines = get_added_lines()

        comment_lines = [
            line for line in added_lines
            if line.startswith("--") or line.startswith("//")
        ]

        jira_keys = sorted({
            match.group(0).upper()
            for line in comment_lines
            for match in JIRA_PATTERN.finditer(line)
        })

        if not jira_keys:
            print("")
            print("Commit rejected.")
            print(
                "No Jira issue key found in newly added "
                "stored procedure comments."
            )
            print("")
            print("Example:")
            print(
                "-- 2026-11-04 -- Author -- AIST-1234 - "
                "Describe the stored procedure change"
            )
            print("")
            return 1

        print("")
        print("Validating stored procedure Jira references...")
        print("")

        if not asyncio.run(validate_jira_issues(jira_keys)):
            print("")
            print("Commit rejected.")
            print("Please use a valid Jira issue key.")
            print("")
            return 1

        print("")
        print("Stored procedure validation successful.")
        print("")
        return 0

    except JiraAuthenticationError as exc:
        print("")
        print("Jira authentication or permission failed.")
        print(str(exc))
        print("Run: aistctl renew")
        print("")
        return 1

    except JiraConnectionError as exc:
        print("")
        print("Unable to connect to Jira.")
        print(str(exc))
        print("Check your network connection and try again.")
        print("")
        return 1

    except JiraRateLimitError as exc:
        print("")
        print("Jira rate limit exceeded.")
        print(str(exc))
        print("")
        return 1

    except JiraUnexpectedResponseError as exc:
        print("")
        print("Unexpected response from Jira.")
        print(str(exc))
        print("")
        return 1

    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print("")
        print("Unable to validate stored procedure changes.")
        print(f"Reason: {exc}")
        print("")
        return 1


if __name__ == "__main__":
    raise SystemExit(validate_stored_procedures())

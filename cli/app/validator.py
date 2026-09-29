import re
from typing import Optional

from app.jira import (
    JiraAuthenticationError,
    JiraConnectionError,
    JiraRateLimitError,
    JiraUnexpectedResponseError,
)


JIRA_KEY_PATTERN = re.compile(
    r"\b(AIST-\d+)\b",
    re.IGNORECASE,
)


def extract_jira_key(
    commit_message: str,
) -> Optional[str]:
    """
    Extract an AIST Jira issue key from the commit message.
    """

    match = JIRA_KEY_PATTERN.search(commit_message)

    if not match:
        return None

    return match.group(1).upper()


async def validate_commit(
    commit_message: str,
    jira_client,
):
    """
    Validate a Git commit message.

    Rules:
    1. Commit message must contain AIST-<number>.
    2. Jira credentials must be valid.
    3. The Jira issue must exist.
    """

    jira_key = extract_jira_key(commit_message)

    if not jira_key:
        return {
            "valid": False,
            "jira_key": None,
            "error_type": "missing_issue_key",
            "reason": (
                "Commit message must contain a Jira "
                "issue key in the format AIST-1234."
            ),
        }

    # Validate Jira credentials first. This prevents an invalid
    # credential from being mistaken for a missing issue.
    try:
        await jira_client.validate_credentials()

    except JiraAuthenticationError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_authentication",
            "reason": str(exc),
        }

    except JiraConnectionError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_connection",
            "reason": str(exc),
        }

    except JiraRateLimitError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_rate_limit",
            "reason": str(exc),
        }

    except JiraUnexpectedResponseError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_unexpected_response",
            "reason": str(exc),
        }

    except Exception as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_error",
            "reason": f"Unable to validate Jira credentials: {exc}",
        }

    # Credentials are valid. Now check whether the issue exists.
    try:
        exists = await jira_client.issue_exists(jira_key)

    except JiraAuthenticationError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_authentication",
            "reason": str(exc),
        }

    except JiraConnectionError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_connection",
            "reason": str(exc),
        }

    except JiraRateLimitError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_rate_limit",
            "reason": str(exc),
        }

    except JiraUnexpectedResponseError as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_unexpected_response",
            "reason": str(exc),
        }

    except Exception as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_error",
            "reason": (
                f"Unable to validate {jira_key} with Jira: {exc}"
            ),
        }

    if not exists:
        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "issue_not_found",
            "reason": (
                f"{jira_key} does not exist in Jira."
            ),
        }

    return {
        "valid": True,
        "jira_key": jira_key,
        "error_type": None,
        "reason": (
            f"{jira_key} exists in Jira."
        ),
    }

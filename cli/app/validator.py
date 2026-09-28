import re
from typing import Optional


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

    match = JIRA_KEY_PATTERN.search(
        commit_message,
    )

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

    jira_key = extract_jira_key(
        commit_message,
    )

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

    # Validate Jira credentials before checking the issue.
    # This prevents Jira from returning a 404 for an issue
    # when the real problem is authentication or permission.
    try:
        await jira_client.validate_credentials()

    except Exception as exc:
        error_message = str(exc).lower()

        if "authentication or permission failed" in error_message:
            return {
                "valid": False,
                "jira_key": jira_key,
                "error_type": "jira_authentication",
                "reason": (
                    "Jira authentication or permission failed."
                ),
            }

        if (
            "timed out" in error_message
            or "unable to reach jira" in error_message
            or "unable to connect to jira" in error_message
        ):
            return {
                "valid": False,
                "jira_key": jira_key,
                "error_type": "jira_connection",
                "reason": str(exc),
            }

        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_error",
            "reason": (
                f"Unable to validate Jira credentials: "
                f"{exc}"
            ),
        }

    # Credentials are valid. Now check whether the issue exists.
    try:
        exists = await jira_client.issue_exists(
            jira_key,
        )

    except Exception as exc:
        error_message = str(exc).lower()

        if (
            "timed out" in error_message
            or "unable to reach jira" in error_message
            or "unable to connect to jira" in error_message
        ):
            return {
                "valid": False,
                "jira_key": jira_key,
                "error_type": "jira_connection",
                "reason": str(exc),
            }

        return {
            "valid": False,
            "jira_key": jira_key,
            "error_type": "jira_error",
            "reason": (
                f"Unable to validate {jira_key} with Jira: "
                f"{exc}"
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
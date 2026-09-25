import re
from typing import Optional


JIRA_KEY_PATTERN = re.compile(
    r"\b(AIST-\d+)\b",
    re.IGNORECASE,
)


def extract_jira_key(
    commit_message: str,
) -> Optional[str]:
    match = JIRA_KEY_PATTERN.search(commit_message)

    if not match:
        return None

    return match.group(1).upper()


async def validate_commit(
    commit_message: str,
    jira_client,
):
    jira_key = extract_jira_key(commit_message)

    if not jira_key:
        return {
            "valid": False,
            "jira_key": None,
            "reason": (
                "Commit message must contain a Jira "
                "issue key in the format AIST-1234."
            ),
        }

    try:
        exists = await jira_client.issue_exists(
            jira_key
        )
    except Exception as exc:
        return {
            "valid": False,
            "jira_key": jira_key,
            "reason": (
                f"Unable to validate {jira_key} "
                f"with Jira: {exc}"
            ),
        }

    if not exists:
        return {
            "valid": False,
            "jira_key": jira_key,
            "reason": (
                f"{jira_key} does not exist in Jira."
            ),
        }

    return {
        "valid": True,
        "jira_key": jira_key,
        "reason": (
            f"{jira_key} exists in Jira."
        ),
    }
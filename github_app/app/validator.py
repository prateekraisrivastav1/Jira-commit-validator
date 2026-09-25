import re
from typing import Optional


JIRA_KEY_PATTERN = re.compile(
    r"\b([A-Z][A-Z0-9]+-\d+)\b",
    re.IGNORECASE
)


def extract_jira_key(commit_message: str) -> Optional[str]:
    match = JIRA_KEY_PATTERN.search(commit_message)
    if not match:
        return None
    return match.group(1).upper()

async def validate_commit(
    commit_message: str,
    jira_client
):
    jira_key = extract_jira_key(commit_message)
    if not jira_key:
        return {
            "valid": False,
            "jira_key": None,
            "reason": "Commit message does not contain a Jira issue key."
        }
    exists = await jira_client.contains_issue(jira_key)

    if not exists:
        return {
            "valid": False,
            "jira_key": jira_key,
            "reason": (
                f"{jira_key} is not part of the configured sprint."
            )
        }
    return {
        "valid": True,
        "jira_key": jira_key,
        "reason": f"{jira_key} is valid for the current sprint."
    }
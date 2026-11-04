import re
import subprocess

JIRA_PATTERN = re.compile(r"\bAIST-\d+\b")

def get_added_lines():
    result = subprocess.run(
        [
            "git", "diff",
            "--cached",
            "--no-ext-diff",
            "--unified=0",
            "--",
            "snowflake/storedprocs/"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    added_lines = []

    for line in result.stdout.splitlines():
        # Ignore diff metadata and removed lines
        if line.startswith("+++") or not line.startswith("+"):
            continue

        added_lines.append(line[1:].strip())

    return added_lines


def validate_sql_jira_comment():
    added_lines = get_added_lines()

    # Only inspect newly added SQL comment lines
    comment_lines = [
        line for line in added_lines
        if line.startswith("--") or line.startswith("//")
    ]

    jira_comments = [
        line for line in comment_lines
        if JIRA_PATTERN.search(line)
    ]

    if not jira_comments:
        print(
            "Validation failed: No Jira key found in newly added "
            "stored procedure comments."
        )
        return False

    print("New stored procedure Jira comments:")
    for comment in jira_comments:
        print(comment)

    return True

if __name__ == "__main__":
    success = validate_sql_jira_comment()
    raise SystemExit(0 if success else 1)
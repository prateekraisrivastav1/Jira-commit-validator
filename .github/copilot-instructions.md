
## Git Commit Message Guidelines

Every commit message must contain a Jira issue key matching this regular expression:

\bAIST-\d+\b

Rules:
- The Jira issue key can appear anywhere in the commit message.
- The issue key must follow the AIST- followed by one or more digits format.
- Do not invent Jira issue keys.
- Prefer the Jira issue key from the current branch name.
- If no Jira issue key is available, ask the developer to provide one.
- Always generate a descriptive commit message.

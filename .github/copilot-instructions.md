# Commit Message Instructions

Generate a concise Git commit message based on the staged changes.

Requirements:

1. The commit message MUST contain a Jira issue key matching:
   `\bAIST-\d+\b`

2. The Jira key can appear anywhere in the commit message.

3. Prefer the Jira key from the current branch name.

4. Never invent a Jira issue key.

5. If no Jira issue key is available, ask the developer to provide one.

6. Describe the actual code changes clearly.

7. Use imperative wording.

8. Keep the message concise.

Example:
Fix premium calculation logic AIST-1234

Do not generate a message without a Jira issue key.

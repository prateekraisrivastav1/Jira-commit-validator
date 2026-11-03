
# AIST Commit and SQL Change History Validation

Review staged Git changes before committing.

## 1. Commit Message Validation

Every commit message must contain a Jira issue key matching:

\bAIST-\d+\b

The Jira key can appear anywhere in the commit message.

## 2. SQL Stored Procedure Validation

For every newly added or modified SQL stored procedure:

- Inspect the Git diff.
- Identify newly added change-history comments.
- Require a change-history entry for the modification.
- Do not count existing historical comments as new entries.

The change-history entry must contain:
- Date in YYYY-MM-DD format.
- Developer/author name.
- Jira issue key.
- Description of the change.

Expected format:

//YYYY-MM-DD -- Author Name -- AIST-1234 - Description of change

Accept existing variations in comment formatting where the same information is present.

## 3. Cross-validation

The Jira key in the SQL change-history comment MUST match the Jira key in the commit message.

Example:

Commit message:
Fix premium calculation AIST-1234

SQL history comment:
//2026-10-22 -- Prateek -- AIST-1234 - Fix premium calculation

This is valid.

If the commit message contains AIST-1234 but the SQL comment contains AIST-6, flag the mismatch.

## 4. Reporting

For every validation failure, report:
- File name.
- Stored procedure name.
- Commit message Jira key.
- SQL comment Jira key.
- Specific validation failure.
- Suggested correction.

Do not modify files automatically. Only report issues and suggestions.

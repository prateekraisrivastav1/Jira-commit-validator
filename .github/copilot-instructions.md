# AIST Git Commit Message and SQL Change Validation Guidelines

## 1. Purpose

These instructions define the commit message convention and SQL stored procedure change-history requirements for this repository.

Every commit must reference a valid Jira issue key in the commit message.

When SQL stored procedures are created or modified, the corresponding SQL change-history comment must also contain the same Jira issue key.

Follow these instructions whenever generating commit messages or reviewing code changes.

---

## 2. Git Commit Message Format

Every commit message MUST contain a Jira issue key matching this regular expression:

`\bAIST-\d+\b`

The Jira issue key can appear anywhere in the commit message.

### Recommended commit message structure

`<Short descriptive summary> <JIRA-ISSUE-KEY>`

Examples:

- Fix premium calculation logic AIST-1234
- Update stored procedure for policy validation AIST-456
- Add missing null checks AIST-789
- Refactor deployment configuration AIST-6

### Commit message requirements

1. Always include one Jira issue key.
2. The Jira key must start with `AIST-`, followed by one or more digits.
3. The Jira key may appear at the beginning, middle, or end of the message.
4. Write a meaningful description of the code change.
5. Use clear, concise language.
6. Prefer imperative wording, such as Add, Fix, Update, Remove, Refactor, or Implement.
7. Do not generate generic messages such as "Updated files", "Changes", or "Code changes".
8. Do not invent Jira issue numbers.
9. If the Jira issue key is available in the current branch name, use that key.
10. If the branch does not contain a Jira issue key, ask the developer to provide one.
11. Do not assume that a Jira issue key found in an unrelated file is the correct issue for the commit.
12. Do not generate a commit message without a Jira issue key.

### Commit message examples

VALID:

- Fix premium calculation logic AIST-1234
- AIST-1234 Fix premium calculation logic
- Update policy validation for missing records AIST-6
- Refactor stored procedure AIST-456

INVALID:

- Fix premium calculation logic
- Updated files
- AIST-ABC Fix premium calculation
- Fix premium calculation AIST-
- AIST-1234

The commit message must contain both a Jira reference and a meaningful description.

---

## 3. Commit Message Generation Instructions

When asked to generate a commit message:

1. Inspect the staged changes or the supplied Git diff.
2. Understand what functionality has been added, modified, or removed.
3. Identify the Jira issue key from the current branch name, if available.
4. Generate a concise commit message describing the actual changes.
5. Include the Jira issue key in the message.
6. Verify that the message matches the required Jira key pattern.
7. Ensure that the description accurately represents the code changes.

IMPORTANT OUTPUT REQUIREMENTS:

- Return a plain-text Git commit message.
- Do not return JSON.
- Do not return XML.
- Do not wrap the commit message in Markdown code fences.
- Do not include explanations, introductions, or additional commentary.
- Do not include labels such as "Generated commit message:".
- Do not invent a Jira issue key.
- If the Jira key is unavailable, ask the developer to provide it instead of generating a final commit message.

Example of the expected output:

Fix premium calculation logic AIST-1234

---

## 4. SQL Stored Procedure Change-History Validation

Whenever SQL stored procedure files are added or modified, inspect the Git diff and review the relevant changes.

The existing SQL files contain procedure documentation and historical change comments.

Preserve the existing documentation structure and formatting.

Do not introduce a completely new documentation format.

### Change-history requirements

Every newly created or modified stored procedure must have an appropriate new change-history entry.

The entry must contain:

1. Change date.
2. Developer or author name.
3. Jira issue key.
4. Description of the modification.

### Expected change-history format

`//YYYY-MM-DD -- Author Name -- AIST-1234 - Description of change`

Example:

`//2026-11-03 -- Prateek -- AIST-1234 - Updated premium calculation logic`

Existing variations in spacing and comment formatting may be accepted as long as all required information is present.

### SQL procedure documentation example

```sql
// PROCEDURE :    act_DEV_conf.agi.update_premium_records
// CREATION DATE : 03/11/2026
// DESCRIPTION :   Update premium records based on revised business rules
// AUTHOR:         Prateek
// TYPE :          SQL
//------------------------------------------------------------
// VERSION: 1.0
// AUTHOR: Prateek
//------------------------------------------------------------
// DESCRIPTION: Update premium calculation and validation logic
//------------------------------------------------------------
// INPUTS
//    TABLES: act_DEV_conf.agi.premium_records
//    PARAMETERS: POLICY_ID, PREMIUM_AMOUNT
// OUTPUTS
//    RETURNS: Updated premium records
//------------------------------------------------------------
// CHANGE HISTORY:
// 2026-11-03 -- Prateek -- AIST-1234 - Updated premium calculation logic
```

---

## 5. SQL Change-History Validation Rules

When reviewing SQL changes:

1. Identify newly added and modified stored procedures.
2. Inspect the actual Git diff.
3. Verify that a new change-history entry has been added for each affected procedure.
4. Verify that the entry contains a date, author, Jira key, and meaningful description.
5. Do not treat an old historical comment elsewhere in the file as a new change-history entry.
6. For newly created procedures, require the appropriate procedure documentation and change-history entry.
7. For modified procedures, preserve existing documentation and add a new history entry.
8. Do not remove or rewrite historical entries unless explicitly requested.
9. Do not automatically modify source files without developer approval.

---

## 6. Jira Cross-Validation

The Jira issue key in the commit message and the Jira issue key in each newly added SQL change-history entry MUST match.

Example:

Commit message:

`Fix premium calculation logic AIST-1234`

SQL change-history entry:

`//2026-11-03 -- Prateek -- AIST-1234 - Updated premium calculation logic`

Result: VALID.

### Mismatch example

Commit message:

`Fix premium calculation logic AIST-1234`

SQL change-history entry:

`//2026-11-03 -- Prateek -- AIST-6 - Updated premium calculation logic`

Result: INVALID.

Report the mismatch and suggest the correct Jira reference.

---

## 7. Copilot Code Review Behaviour

When asked to review changes before committing:

- Review the staged Git diff.
- Identify changed SQL stored procedure files.
- Check the commit message against the Jira key requirement.
- Check new SQL change-history entries.
- Compare the Jira references in the commit message and SQL comments.
- Identify missing or inconsistent information.
- Explain each validation failure clearly.
- Suggest corrections without modifying files automatically.

Do not claim that a Jira issue exists based only on its format. Actual Jira issue existence is verified separately by the AIST Git Validator CLI.

---

## 8. Expected Validation Report

If all checks pass:

AIST Commit Review: PASS

- Commit message contains a Jira issue key.
- SQL change-history entries are present where required.
- Jira references match.
- Change descriptions are present.

If validation fails:

AIST Commit Review: FAILED

File: update_premium_records.sql

Procedure: update_premium_records

Issue:
The Jira key in the SQL change-history comment does not match the commit message.

Commit message Jira key: AIST-1234

SQL comment Jira key: AIST-6

Suggested correction:
Update the SQL change-history entry to reference AIST-1234.

---

## 9. Important Separation of Responsibilities

Copilot provides commit message generation assistance and code review suggestions.

The AIST Git Validator CLI remains responsible for deterministic commit-message validation and Jira issue existence checks.

Copilot instructions are guidance and must not be treated as a replacement for Git hook enforcement.

Always prioritize accurate descriptions of actual code changes over generating generic commit messages.
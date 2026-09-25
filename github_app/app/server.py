import hashlib
import hmac
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request

from app.github import GitHubClient
from app.jira import JiraClient
from app.validator import validate_commit


load_dotenv()


app = FastAPI(
    title="AIST GitHub Commit Validator"
)


jira = JiraClient()
github = GitHubClient()


def verify_github_signature(
    payload: bytes,
    signature: str | None,
) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    if not secret or not signature:
        return False

    expected_signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(
        expected_signature,
        signature,
    )


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
):
    payload = await request.body()

    if not verify_github_signature(
        payload,
        x_hub_signature_256,
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid GitHub webhook signature",
        )

    if not x_github_event:
        raise HTTPException(
            status_code=400,
            detail="Missing X-GitHub-Event header",
        )

    if x_github_event == "ping":
        return {
            "status": "ok",
            "event": "ping",
        }

    if x_github_event != "push":
        return {
            "status": "ignored",
            "event": x_github_event,
        }

    try:
        body = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        )

    if body.get("deleted"):
        return {
            "status": "ignored",
            "event": "push",
            "reason": "Branch was deleted",
        }

    installation = body.get("installation") or {}
    repository = body.get("repository") or {}

    installation_id = installation.get("id")
    owner = (repository.get("owner") or {}).get("login")
    repo = repository.get("name")

    if not installation_id:
        raise HTTPException(
            status_code=400,
            detail="Missing GitHub App installation ID",
        )

    if not owner or not repo:
        raise HTTPException(
            status_code=400,
            detail="Missing repository owner or name",
        )

    commits = body.get("commits") or []

    if not commits:
        return {
            "status": "ok",
            "event": "push",
            "validated": 0,
            "message": "No commits to validate",
        }

    installation_token = await github.get_installation_token(
        int(installation_id)
    )

    results = []

    for commit in commits:
        sha = commit.get("id")
        message = commit.get("message")

        if not sha or not message:
            results.append({
                "sha": sha,
                "valid": False,
                "reason": "Commit payload is missing SHA or message",
            })
            continue

        result = await validate_commit(
            message,
            jira,
        )

        conclusion = (
            "success"
            if result["valid"]
            else "failure"
        )

        title = (
            "Jira commit validation passed"
            if result["valid"]
            else "Jira commit validation failed"
        )

        await github.create_check(
            installation_token=installation_token,
            owner=owner,
            repo=repo,
            sha=sha,
            conclusion=conclusion,
            title=title,
            summary=result["reason"],
        )

        results.append({
            "sha": sha,
            "message": message,
            **result,
        })

    return {
        "status": "ok",
        "event": "push",
        "repository": f"{owner}/{repo}",
        "validated": len(results),
        "results": results,
    }
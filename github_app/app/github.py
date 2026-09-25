import os
import time

import httpx
import jwt


GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"


class GitHubClient:

    def __init__(self):
        self.app_id = os.environ["GITHUB_APP_ID"]

        with open(
            os.environ["GITHUB_PRIVATE_KEY_PATH"],
            "r",
        ) as f:
            self.private_key = f.read()

    def create_jwt(self):
        now = int(time.time())

        payload = {
            "iat": now - 60,
            "exp": now + 540,
            "iss": self.app_id,
        }

        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
        )

    async def get_installation_token(
        self,
        installation_id: int,
    ):
        app_jwt = self.create_jwt()

        url = (
            f"{GITHUB_API}/app/installations/"
            f"{installation_id}/access_tokens"
        )

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {app_jwt}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                timeout=30,
            )

            response.raise_for_status()

            return response.json()["token"]

    async def create_check(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        sha: str,
        conclusion: str,
        title: str,
        summary: str,
    ):
        url = (
            f"{GITHUB_API}/repos/"
            f"{owner}/{repo}/check-runs"
        )

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": (
                f"Bearer {installation_token}"
            ),
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

        body = {
            "name": "Jira Commit Validation",
            "head_sha": sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": title,
                "summary": summary,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=body,
                timeout=30,
            )

            response.raise_for_status()

            return response.json()

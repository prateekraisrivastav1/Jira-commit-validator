import os

import httpx


class JiraClient:

    def __init__(self):
        self.base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
        self.email = os.environ["JIRA_EMAIL"]
        self.api_token = os.environ["JIRA_API_TOKEN"]

    async def issue_exists(self, issue_key: str) -> bool:
        url = (
            f"{self.base_url}/rest/api/3/issue/"
            f"{issue_key}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={"fields": "key"},
                auth=(self.email, self.api_token),
                headers={
                    "Accept": "application/json",
                },
                timeout=10,
            )

        if response.status_code == 200:
            return True

        if response.status_code == 404:
            return False

        if response.status_code in (401, 403):
            raise RuntimeError(
                "Jira authentication or permission failed."
            )

        response.raise_for_status()

        return False
import os
import time
from typing import Set

import httpx


class JiraClient:

    def __init__(self):
        self.base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
        self.email = os.environ["JIRA_EMAIL"]
        self.api_token = os.environ["JIRA_API_TOKEN"]
        self.board_id = os.environ["JIRA_BOARD_ID"]

        self._sprint_keys: Set[str] = set()
        self._cache_timestamp = 0

        self.cache_ttl = int(
            os.getenv("CACHE_TTL_SECONDS", "300")
        )

    async def get_current_sprint_issues(self) -> Set[str]:
        """
        Fetch all issues from the configured sprint.
        """

        sprint_id = os.environ["JIRA_SPRINT_ID"]

        url = (
            f"{self.base_url}/rest/agile/1.0/"
            f"board/{self.board_id}/sprint/{sprint_id}/issue"
        )

        start_at = 0
        issue_keys = set()

        async with httpx.AsyncClient() as client:

            while True:

                response = await client.get(
                    url,
                    params={
                        "startAt": start_at,
                        "maxResults": 100,
                        "fields": "key,issuetype",
                    },
                    auth=(self.email, self.api_token),
                    headers={
                        "Accept": "application/json"
                    },
                    timeout=30,
                )

                response.raise_for_status()

                data = response.json()

                issues = data.get("issues", [])

                for issue in issues:
                    issue_keys.add(issue["key"].upper())

                if len(issues) < 100:
                    break

                start_at += len(issues)

        return issue_keys

    async def refresh_cache(self) -> Set[str]:

        now = time.time()

        if (
            self._sprint_keys
            and now - self._cache_timestamp < self.cache_ttl
        ):
            return self._sprint_keys

        self._sprint_keys = (
            await self.get_current_sprint_issues()
        )

        self._cache_timestamp = now

        return self._sprint_keys

    async def contains_issue(self, issue_key: str) -> bool:

        issues = await self.refresh_cache()

        return issue_key.upper() in issues
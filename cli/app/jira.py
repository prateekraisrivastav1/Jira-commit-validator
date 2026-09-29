import json
import os
from pathlib import Path

import httpx


def get_config_path() -> Path:
    return Path.home() / ".aist" / "config.json"


def load_config() -> dict:
    config_path = get_config_path()

    if not config_path.exists():
        return {}

    try:
        return json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid AIST configuration file: {config_path}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read AIST configuration file: {config_path}. "
            f"Reason: {exc}"
        ) from exc


class JiraAuthenticationError(RuntimeError):
    """Jira rejected the configured credentials or permissions."""


class JiraConnectionError(RuntimeError):
    """The Jira server could not be reached."""


class JiraRateLimitError(RuntimeError):
    """Jira rate-limited the request."""


class JiraUnexpectedResponseError(RuntimeError):
    """Jira returned an unexpected HTTP response."""


class JiraClient:
    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        config = load_config()

        if base_url is None:
            base_url = config.get("jira_base_url")

        if email is None:
            email = config.get("jira_email")

        if api_token is None:
            api_token = config.get("jira_api_token")

        if base_url is None:
            base_url = os.getenv("JIRA_BASE_URL")

        if email is None:
            email = os.getenv("JIRA_EMAIL")

        if api_token is None:
            api_token = os.getenv("JIRA_API_TOKEN")

        if not base_url:
            raise RuntimeError(
                "Jira Base URL is not configured. "
                "Run: aistctl setup"
            )

        if not email:
            raise RuntimeError(
                "Jira email is not configured. "
                "Run: aistctl setup"
            )

        if not api_token:
            raise RuntimeError(
                "Jira API token is not configured. "
                "Run: aistctl setup"
            )

        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token

    @staticmethod
    def _raise_for_response(
        response: httpx.Response,
        operation: str,
    ) -> None:
        status = response.status_code

        if status in (401, 403):
            raise JiraAuthenticationError(
                "Jira authentication or permission failed."
            )

        if status == 429:
            raise JiraRateLimitError(
                "Jira rate limit exceeded. "
                "Please wait and try again."
            )

        raise JiraUnexpectedResponseError(
            f"Jira returned HTTP {status} while {operation}."
        )

    async def validate_credentials(self) -> bool:
        """
        Validate the configured Jira credentials.
        """

        url = f"{self.base_url}/rest/api/3/myself"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    auth=(self.email, self.api_token),
                    headers={"Accept": "application/json"},
                    timeout=10,
                )
        except httpx.TimeoutException as exc:
            raise JiraConnectionError(
                "Unable to reach Jira. The request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise JiraConnectionError(
                "Unable to connect to Jira."
            ) from exc

        if response.status_code == 200:
            return True

        self._raise_for_response(
            response,
            "validating Jira credentials",
        )
        return False

    async def issue_exists(self, issue_key: str) -> bool:
        """
        Check whether the Jira issue exists in the configured
        Jira organization.
        """

        url = (
            f"{self.base_url}/rest/api/3/"
            f"issue/{issue_key}"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params={"fields": "key"},
                    auth=(self.email, self.api_token),
                    headers={"Accept": "application/json"},
                    timeout=10,
                )
        except httpx.TimeoutException as exc:
            raise JiraConnectionError(
                "Jira request timed out. Unable to reach Jira."
            ) from exc
        except httpx.RequestError as exc:
            raise JiraConnectionError(
                "Unable to connect to Jira."
            ) from exc

        if response.status_code == 200:
            return True

        if response.status_code == 404:
            return False

        self._raise_for_response(
            response,
            f"checking Jira issue {issue_key}",
        )
        return False

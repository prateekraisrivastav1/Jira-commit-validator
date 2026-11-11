"""Download and safely install the latest public AIST validator release."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

OWNER = "prateekraisrivastav1"
REPOSITORY = "aistctl-releases"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPOSITORY}/releases/latest"
ASSET_NAME = "aist-validator.exe"
VERSION_FILE = "validator-version.json"


def install_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1] / "dist"


def validator_path() -> Path:
    return install_directory() / ASSET_NAME


def _version_tuple(value: str) -> tuple:
    parts = value.strip().lstrip("vV").split(".")
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        raise RuntimeError(f"Invalid release version: {value}")


def _local_version() -> str:
    path = install_directory() / VERSION_FILE
    if not path.exists():
        return "0.0.0"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version", "0.0.0")
    except (OSError, json.JSONDecodeError):
        return "0.0.0"


def update_validator(quiet: bool = False) -> int:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
            response = client.get(API_URL)
            response.raise_for_status()
            release = response.json()
            latest = release.get("tag_name", "").lstrip("vV")
            if not latest:
                raise RuntimeError("Latest GitHub release has no tag name.")
            if _version_tuple(latest) <= _version_tuple(_local_version()):
                if not quiet:
                    print(f"Validator is up to date ({_local_version()}).")
                return 0

            assets = {asset["name"]: asset["browser_download_url"] for asset in release.get("assets", [])}
            if ASSET_NAME not in assets or f"{ASSET_NAME}.sha256" not in assets:
                raise RuntimeError("Release is missing the executable or SHA-256 checksum asset.")
            binary_response = client.get(assets[ASSET_NAME])
            binary_response.raise_for_status()
            checksum_response = client.get(assets[f"{ASSET_NAME}.sha256"])
            checksum_response.raise_for_status()

        data = binary_response.content
        expected = checksum_response.text.strip().split()[0].lower()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise RuntimeError("Validator checksum verification failed; existing version was not changed.")

        target = validator_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".exe.download")
        backup = target.with_suffix(".exe.previous")
        version_path = target.parent / VERSION_FILE
        version_temp = version_path.with_suffix(".json.tmp")
        try:
            temp.write_bytes(data)
            if target.exists():
                if backup.exists():
                    backup.unlink()
                os.replace(target, backup)
            os.replace(temp, target)
            version_temp.write_text(json.dumps({"version": latest}, indent=2), encoding="utf-8")
            os.replace(version_temp, version_path)
        except Exception:
            if target.exists():
                target.unlink()
            if backup.exists():
                os.replace(backup, target)
            raise
        if not quiet:
            print(f"Validator updated successfully: {latest}")
        return 0
    except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
        if not quiet:
            print(f"Validator update failed: {exc}")
            print("The currently installed validator has been retained.")
        return 1


def run_validator() -> int:
    executable = validator_path()
    if not executable.is_file():
        print("The stored procedure validator executable is missing.")
        print("Run: aistctl update")
        return 1
    try:
        return subprocess.run([str(executable)], check=False).returncode
    except OSError as exc:
        print(f"Unable to start stored procedure validator: {exc}")
        return 1


def install_update_task() -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    command = ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", "09:00", "/TN", "AIST Validator Update", "/TR", f'"{sys.executable}" update --quiet']
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print("Unable to create the daily update task.")
        if result.stderr.strip():
            print(result.stderr.strip())
    else:
        print("Daily validator update check scheduled at 09:00.")


def remove_update_task() -> None:
    if os.name == "nt":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", "AIST Validator Update"], capture_output=True, text=True)

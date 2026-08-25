#!/usr/bin/env python3
"""
refresh_token.py

Instagram long-lived access tokens expire after ~60 days. This script
exchanges the current token for a fresh 60-day token, then updates the
IG_ACCESS_TOKEN secret in your GitHub repo automatically so you never
have to do it by hand.

Required environment variables:
  IG_ACCESS_TOKEN      Current long-lived token (about to expire)
  IG_APP_SECRET         Your Meta App Secret
  GH_ADMIN_TOKEN         A GitHub Personal Access Token with "repo" scope
                          (needs permission to write Actions secrets)
  GITHUB_REPOSITORY      e.g. "yourname/instagram-scheduler" (auto-set in Actions)

Optional:
  GRAPH_API_VERSION      Defaults to "v21.0"
"""

import os
import sys
import base64
import requests
from nacl import encoding, public

GRAPH_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")


def env_or_die(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: missing required environment variable {name}", file=sys.stderr)
        sys.exit(1)
    return val


def refresh_long_lived_token(current_token: str, app_secret: str) -> str:
    # Instagram Graph API's dedicated refresh endpoint (graph.instagram.com)
    resp = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={
            "grant_type": "ig_refresh_token",
            "access_token": current_token,
        },
        timeout=30,
    )
    data = resp.json()
    if "access_token" not in data:
        print(f"Direct refresh failed ({data}), trying Facebook token exchange fallback...")
        return exchange_via_fb_graph(current_token, app_secret)
    print(f"Refreshed token, expires in {data.get('expires_in')} seconds")
    return data["access_token"]


def exchange_via_fb_graph(current_token: str, app_secret: str) -> str:
    app_id = env_or_die("IG_APP_ID")
    resp = requests.get(
        f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": current_token,
        },
        timeout=30,
    )
    data = resp.json()
    if "access_token" not in data:
        print(f"ERROR: token refresh failed: {data}", file=sys.stderr)
        sys.exit(1)
    return data["access_token"]


def get_repo_public_key(repo: str, gh_token: str) -> tuple[str, str]:
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    data = resp.json()
    return data["key"], data["key_id"]


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_github_secret(repo: str, gh_token: str, secret_name: str, new_value: str) -> None:
    key_b64, key_id = get_repo_public_key(repo, gh_token)
    encrypted_value = encrypt_secret(key_b64, new_value)
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
        json={"encrypted_value": encrypted_value, "key_id": key_id},
        timeout=30,
    )
    if resp.status_code not in (201, 204):
        print(f"ERROR updating secret: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    print(f"Updated GitHub secret {secret_name} successfully.")


def main() -> None:
    current_token = env_or_die("IG_ACCESS_TOKEN")
    app_secret = env_or_die("IG_APP_SECRET")
    gh_token = env_or_die("GH_ADMIN_TOKEN")
    repo = env_or_die("GITHUB_REPOSITORY")

    new_token = refresh_long_lived_token(current_token, app_secret)
    update_github_secret(repo, gh_token, "IG_ACCESS_TOKEN", new_token)


if __name__ == "__main__":
    main()

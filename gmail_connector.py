"""
InboxIQ — Gmail Connector Module
Handles OAuth2 authentication and email fetching from Gmail API.
"""

import os
import base64
import logging
import time
from email import message_from_bytes

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger("InboxIQ")

# Gmail API read-only scope
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailConnector:
    """Authenticates with Gmail API and fetches email payloads."""

    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None

    def _authenticate(self):
        """Perform OAuth2 flow, returning an authenticated Gmail API service."""
        creds = None

        # Load existing token if available
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load token file: {e}")

        # Refresh or obtain new credentials
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("OAuth token refreshed successfully.")
            except Exception as e:
                logger.warning(f"Token refresh failed ({e}), re-authenticating.")
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"credentials.json not found at '{self.credentials_path}'. "
                    "Download it from Google Cloud Console > APIs & Services > Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("New OAuth credentials obtained via browser flow.")

        # Save token for future runs
        with open(self.token_path, "w") as f:
            f.write(creds.to_json())
        logger.info(f"Token saved to {self.token_path}")

        self.service = build("gmail", "v1", credentials=creds)
        return self.service

    def _decode_email_snippet(self, payload: dict) -> str:
        """Extract and decode the email body text from a Gmail API payload."""
        body_text = ""

        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] in ("text/plain", "text/html"):
                    data = part["body"].get("data", "")
                    if data:
                        try:
                            decoded = base64.urlsafe_b64decode(data.encode("ASCII"))
                            body_text = decoded.decode("utf-8", errors="replace")
                        except Exception:
                            continue
                        break
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data.encode("ASCII"))
                    body_text = decoded.decode("utf-8", errors="replace")
                except Exception:
                    pass

        # Truncate long bodies to avoid token overuse
        if len(body_text) > 2000:
            body_text = body_text[:2000] + "... [truncated]"

        return body_text

    def fetch_latest_emails(self, max_results: int = 50) -> list:
        """
        Fetch the latest emails from the user's primary inbox.

        Returns a list of dicts with keys: sender, subject, date, body, id
        """
        if self.service is None:
            self._authenticate()

        emails = []
        retries = 3

        for attempt in range(retries):
            try:
                # List messages from INBOX
                results = (
                    self.service.users()
                    .messages()
                    .list(userId="me", q="label:INBOX", maxResults=max_results)
                    .execute()
                )
                messages = results.get("messages", [])
                break
            except HttpError as e:
                if attempt < retries - 1:
                    wait = 2 * (attempt + 1)
                    logger.warning(f"Gmail API error listing messages: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"Gmail API failed after {retries} attempts: {e}")
                    return []

        if not messages:
            logger.info("No messages found in inbox.")
            return []

        logger.info(f"Fetched {len(messages)} message IDs from inbox.")

        for msg in messages:
            for attempt in range(retries):
                try:
                    msg_data = (
                        self.service.users()
                        .messages()
                        .get(userId="me", id=msg["id"], format="metadata",
                             metadataHeaders=["From", "Subject", "Date"])
                        .execute()
                    )
                    break
                except HttpError as e:
                    if attempt < retries - 1:
                        wait = 2 * (attempt + 1)
                        logger.warning(f"Gmail API error fetching message {msg['id']}: {e}. Retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        logger.warning(f"Failed to fetch message {msg['id']} after {retries} attempts.")
                        continue

            headers = {}
            for hdr in msg_data.get("payload", {}).get("headers", []):
                headers[hdr["name"].lower()] = hdr["value"]

            body_snippet = self._decode_email_snippet(msg_data.get("payload", {}))

            email = {
                "id": msg["id"],
                "sender": headers.get("from", "Unknown"),
                "subject": headers.get("subject", "(No Subject)"),
                "date": headers.get("date", ""),
                "body": body_snippet,
            }
            emails.append(email)

        logger.info(f"Successfully parsed {len(emails)} emails.")
        return emails

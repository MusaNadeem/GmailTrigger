"""
InboxIQ — LLM Engine Module
Interfaces with OpenAI API to classify emails against tag definitions.
"""

import json
import logging
import time

from openai import OpenAI
from openai import APIConnectionError, APIStatusError, RateLimitError

logger = logging.getLogger("InboxIQ")


class LLMEngine:
    """Classifies email content using OpenAI's chat completions."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def _build_prompt(self, email: dict, tags_config: dict) -> list:
        """Construct the system + user messages for classification."""
        categories = tags_config.get("categories", [])
        default_tag = tags_config.get("default_tag", "General")

        # Build tag definitions string
        tag_definitions = "\n".join(
            f'- "{cat["name"]}": keywords={cat.get("keywords", [])} — {cat.get("description", "")}'
            for cat in categories
        )

        system_prompt = (
            "You are an email classification assistant. Your task is to categorize emails "
            "into exactly one of the provided categories based on the sender, subject, and body content.\n\n"
            f"Available categories:\n{tag_definitions}\n\n"
            f"If no category matches clearly, respond with \"{default_tag}\".\n"
            "Respond with ONLY a single JSON object in this exact format:\n"
            '{"tag": "<category_name>"}\n'
            "Do not include any other text, explanation, or markdown."
        )

        body_preview = email.get("body", "")[:2000]

        user_prompt = (
            f"Sender: {email.get('sender', 'Unknown')}\n"
            f"Subject: {email.get('subject', '(No Subject)')}\n"
            f"Body:\n{body_preview}"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def classify_email(self, email: dict, tags_config: dict) -> str:
        """
        Send an email payload to OpenAI and return the assigned tag string.

        Implements retry with linear backoff on network/server errors.
        """
        messages = self._build_prompt(email, tags_config)
        default_tag = tags_config.get("default_tag", "General")
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=50,
                )

                raw = response.choices[0].message.content.strip()

                # Attempt to parse JSON response
                try:
                    result = json.loads(raw)
                    tag = result.get("tag", default_tag)
                except json.JSONDecodeError:
                    # If response is plain text, use it directly
                    tag = raw.strip().strip('"').strip("'")
                    logger.debug(f"Non-JSON response from LLM, using raw text: '{tag}'")

                # Validate against known categories
                valid_tags = {cat["name"] for cat in tags_config.get("categories", [])}
                if tag not in valid_tags:
                    logger.debug(f"LLM returned unknown tag '{tag}', defaulting to '{default_tag}'")
                    tag = default_tag

                return tag

            except RateLimitError as e:
                wait = 2 * (attempt + 1)
                logger.warning(f"OpenAI rate limited (attempt {attempt + 1}/{max_retries}). Retrying in {wait}s...")
                if attempt < max_retries - 1:
                    time.sleep(wait)
                else:
                    logger.error(f"OpenAI rate limit exceeded after {max_retries} attempts.")
                    return default_tag

            except APIConnectionError as e:
                wait = 2 * (attempt + 1)
                logger.warning(f"OpenAI connection error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s...")
                if attempt < max_retries - 1:
                    time.sleep(wait)
                else:
                    logger.error(f"OpenAI connection failed after {max_retries} attempts.")
                    return default_tag

            except APIStatusError as e:
                logger.error(f"OpenAI API error (status {e.status_code}): {e}")
                return default_tag

            except Exception as e:
                logger.error(f"Unexpected error during LLM classification: {e}")
                return default_tag

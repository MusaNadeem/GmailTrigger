"""
InboxIQ — Gmail Tagger Main Orchestrator
=========================================
Connects to Gmail via OAuth2, fetches recent emails,
classifies them using LLM (OpenAI), and writes results to CSV.

Usage:
    python inboxiq.py

Configuration:
    - .env         : API keys and runtime settings
    - config.yaml  : Provider, model, and output settings
    - tags.yaml    : Classification categories (hot-reloadable)
    - credentials.json : Gmail OAuth2 client secrets (user-provided)
"""

import os
import sys
import logging
import time

from dotenv import load_dotenv

from gmail_connector import GmailConnector
from tag_manager import TagManager
from llm_engine import LLMEngine
from csv_reporter import CSVReporter


def setup_logging(level_name: str = "INFO"):
    """Configure root logger for InboxIQ."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config(config_path: str = "config.yaml") -> dict:
    """Load the YAML-based runtime configuration."""
    try:
        import yaml
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger = logging.getLogger("InboxIQ")
        logger.warning(f"config.yaml not found. Using defaults.")
        cfg = {}
    except Exception as e:
        logger = logging.getLogger("InboxIQ")
        logger.warning(f"Failed to load config.yaml: {e}. Using defaults.")
        cfg = {}

    return {
        "llm_provider": cfg.get("llm_provider", "openai"),
        "max_emails": int(cfg.get("max_emails", 50)),
        "openai_model": cfg.get("openai_model", "gpt-4o-mini"),
        "gemini_model": cfg.get("gemini_model", "gemini-2.0-flash"),
        "output_file": cfg.get("output_file", "results.csv"),
    }


def main():
    # Load environment variables from .env
    load_dotenv()

    # Setup logging
    setup_logging(os.getenv("INBOXIQ_LOG_LEVEL", "INFO"))
    logger = logging.getLogger("InboxIQ")

    logger.info("=" * 60)
    logger.info("InboxIQ Gmail Tagger — Starting batch run")
    logger.info("=" * 60)

    # Validate API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.critical("Missing OPENAI_API_KEY in environment. Create a .env file (see .env.example).")
        sys.exit(1)

    # Load runtime configuration
    config = load_config()
    max_emails = config["max_emails"]
    output_path = os.getenv("INBOXIQ_OUTPUT_PATH", config["output_file"])
    openai_model = config["openai_model"]

    # Phase 1: Load classification tags (hot-reload from YAML)
    logger.info("Phase 1/4: Loading classification tags...")
    tag_mgr = TagManager(config_path="tags.yaml")
    tags_config = tag_mgr.load_tags_config()
    logger.info(f"  → {len(tags_config.get('categories', []))} categories loaded "
                f"(default: '{tags_config.get('default_tag', 'General')}')")

    # Phase 2: Connect to Gmail and fetch emails
    logger.info(f"Phase 2/4: Connecting to Gmail and fetching up to {max_emails} emails...")
    gmail_client = GmailConnector(
        credentials_path="credentials.json",
        token_path="token.json",
    )
    raw_emails = gmail_client.fetch_latest_emails(max_results=max_emails)

    if not raw_emails:
        logger.warning("No emails fetched. Check Gmail connection or inbox contents.")
        sys.exit(0)

    logger.info(f"  → Fetched {len(raw_emails)} emails for classification.")

    # Phase 3: Classify each email using LLM
    logger.info(f"Phase 3/4: Classifying {len(raw_emails)} emails via OpenAI ({openai_model})...")
    llm_classifier = LLMEngine(api_key=api_key, model=openai_model)

    processed_records = []
    for idx, email in enumerate(raw_emails, start=1):
        logger.info(f"  [{idx}/{len(raw_emails)}] Processing: '{email['subject']}'")

        try:
            assigned_tag = llm_classifier.classify_email(email, tags_config)
        except Exception as e:
            logger.error(f"  → Classification failed: {e}")
            assigned_tag = tags_config.get("default_tag", "General")

        record = {
            "sender": email["sender"],
            "subject": email["subject"],
            "date": email["date"],
            "tag": assigned_tag,
        }
        processed_records.append(record)
        logger.info(f"  → Tagged as: [{assigned_tag}]")

        # Small cooldown to avoid rate limits
        if idx < len(raw_emails):
            time.sleep(0.3)

    # Phase 4: Write results to CSV
    logger.info(f"Phase 4/4: Writing {len(processed_records)} records to CSV...")
    reporter = CSVReporter(output_path=output_path)
    reporter.append_to_report(processed_records)

    # Summary
    logger.info("=" * 60)
    logger.info(f"Batch run complete: {len(processed_records)} emails classified.")
    logger.info(f"Results saved to: {output_path}")

    # Tag distribution summary
    tag_counts = {}
    for r in processed_records:
        tag_counts[r["tag"]] = tag_counts.get(r["tag"], 0) + 1
    logger.info("Tag distribution:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {tag}: {count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

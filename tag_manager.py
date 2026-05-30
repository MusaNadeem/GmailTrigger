"""
InboxIQ — Tag Manager Module
Loads and validates classification tags from a YAML configuration file.
Hot-reloadable: reads the file fresh on every call.
"""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("InboxIQ")

# Fallback baseline when YAML is missing or malformed
DEFAULT_TAGS = {
    "version": "1.0",
    "default_tag": "General",
    "categories": [
        {"name": "General", "keywords": [], "description": "Default category for uncategorized emails."},
    ],
}


class TagManager:
    """Reads and validates tag classification rules from a YAML file."""

    def __init__(self, config_path: str = "tags.yaml"):
        self.config_path = config_path

    def load_tags_config(self) -> dict:
        """
        Load and validate the tags configuration file.

        Returns a dictionary with keys: version, default_tag, categories.
        Falls back to DEFAULT_TAGS on error.
        """
        path = Path(self.config_path)

        if not path.exists():
            logger.warning(f"Tags file '{self.config_path}' not found. Using default classification.")
            return dict(DEFAULT_TAGS)

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Validate structure
            if not isinstance(config, dict):
                logger.error(f"Invalid YAML structure in '{self.config_path}': expected a mapping.")
                return dict(DEFAULT_TAGS)

            if "categories" not in config or not isinstance(config["categories"], list):
                logger.error(f"'{self.config_path}' missing 'categories' list. Using defaults.")
                return dict(DEFAULT_TAGS)

            if not config["categories"]:
                logger.warning(f"'{self.config_path}' has empty categories. Using defaults.")
                return dict(DEFAULT_TAGS)

            # Ensure default_tag is present
            if "default_tag" not in config:
                config["default_tag"] = DEFAULT_TAGS["default_tag"]

            # Validate each category
            valid_categories = []
            for i, cat in enumerate(config["categories"]):
                if not isinstance(cat, dict) or "name" not in cat:
                    logger.warning(f"Category at index {i} is malformed — skipping.")
                    continue
                if "keywords" not in cat:
                    cat["keywords"] = []
                if "description" not in cat:
                    cat["description"] = ""
                valid_categories.append(cat)

            if not valid_categories:
                logger.warning("No valid categories found after validation. Using defaults.")
                return dict(DEFAULT_TAGS)

            config["categories"] = valid_categories
            logger.info(
                f"Loaded {len(valid_categories)} tag categories from '{self.config_path}' "
                f"(default: '{config.get('default_tag', 'General')}')"
            )
            return config

        except yaml.YAMLError as e:
            logger.critical(f"YAML parsing error in '{self.config_path}': {e}")
            logger.info("Falling back to default classification tags.")
            return dict(DEFAULT_TAGS)
        except OSError as e:
            logger.critical(f"Failed to read '{self.config_path}': {e}")
            return dict(DEFAULT_TAGS)

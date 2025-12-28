# -*- coding: utf-8 -*-
"""
Custom prompts management for AI Context Studio.

Allows users to customize prompt templates for documentation generation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .constants import CONFIG_DIR
from .models import GenerationType
from .prompt_engine import PromptEngine

logger = logging.getLogger(__name__)

CUSTOM_PROMPTS_FILE: Path = CONFIG_DIR / "custom_prompts.json"


class CustomPromptsManager:
    """
    Manager for custom prompt templates.

    Allows users to override default prompts with custom versions.
    """

    def __init__(self) -> None:
        """Initialize the custom prompts manager."""
        self._custom_prompts: dict[str, str] = {}
        self._custom_system_prompt: Optional[str] = None
        self._load_custom_prompts()

    def _load_custom_prompts(self) -> None:
        """Load custom prompts from file."""
        if not CUSTOM_PROMPTS_FILE.exists():
            return

        try:
            content = CUSTOM_PROMPTS_FILE.read_text(encoding='utf-8')
            data = json.loads(content)
            self._custom_prompts = data.get('prompts', {})
            self._custom_system_prompt = data.get('system_prompt')
            logger.info("Loaded %d custom prompts", len(self._custom_prompts))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load custom prompts: %s", e)

    def save_custom_prompts(self) -> None:
        """Save custom prompts to file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                'prompts': self._custom_prompts,
                'system_prompt': self._custom_system_prompt
            }
            content = json.dumps(data, indent=2, ensure_ascii=False)
            CUSTOM_PROMPTS_FILE.write_text(content, encoding='utf-8')
            logger.info("Saved custom prompts")
        except OSError as e:
            logger.error("Failed to save custom prompts: %s", e)

    def get_system_prompt(self) -> str:
        """Get the system prompt (custom or default)."""
        if self._custom_system_prompt:
            return self._custom_system_prompt
        return PromptEngine.BASE_SYSTEM_PROMPT

    def set_system_prompt(self, prompt: str) -> None:
        """Set a custom system prompt."""
        self._custom_system_prompt = prompt if prompt.strip() else None
        self.save_custom_prompts()

    def get_prompt(self, gen_type: GenerationType) -> str:
        """Get prompt for a generation type (custom or default)."""
        type_key = gen_type.name
        if type_key in self._custom_prompts:
            return self._custom_prompts[type_key]

        # Return default prompt
        if not PromptEngine.GENERATION_PROMPTS:
            PromptEngine._init_prompts()
        return PromptEngine.GENERATION_PROMPTS.get(gen_type, "")

    def set_prompt(self, gen_type: GenerationType, prompt: str) -> None:
        """Set a custom prompt for a generation type."""
        type_key = gen_type.name
        if prompt.strip():
            self._custom_prompts[type_key] = prompt
        elif type_key in self._custom_prompts:
            del self._custom_prompts[type_key]
        self.save_custom_prompts()

    def reset_prompt(self, gen_type: GenerationType) -> None:
        """Reset a prompt to default."""
        type_key = gen_type.name
        if type_key in self._custom_prompts:
            del self._custom_prompts[type_key]
            self.save_custom_prompts()

    def reset_system_prompt(self) -> None:
        """Reset system prompt to default."""
        self._custom_system_prompt = None
        self.save_custom_prompts()

    def reset_all(self) -> None:
        """Reset all prompts to defaults."""
        self._custom_prompts = {}
        self._custom_system_prompt = None
        self.save_custom_prompts()

    def is_prompt_customized(self, gen_type: GenerationType) -> bool:
        """Check if a prompt has been customized."""
        return gen_type.name in self._custom_prompts

    def is_system_prompt_customized(self) -> bool:
        """Check if system prompt has been customized."""
        return self._custom_system_prompt is not None

    def get_default_system_prompt(self) -> str:
        """Get the default system prompt."""
        return PromptEngine.BASE_SYSTEM_PROMPT

    def get_default_prompt(self, gen_type: GenerationType) -> str:
        """Get the default prompt for a generation type."""
        if not PromptEngine.GENERATION_PROMPTS:
            PromptEngine._init_prompts()
        return PromptEngine.GENERATION_PROMPTS.get(gen_type, "")


# Global instance
_custom_prompts_manager: Optional[CustomPromptsManager] = None


def get_custom_prompts_manager() -> CustomPromptsManager:
    """Get the global custom prompts manager instance."""
    global _custom_prompts_manager
    if _custom_prompts_manager is None:
        _custom_prompts_manager = CustomPromptsManager()
    return _custom_prompts_manager

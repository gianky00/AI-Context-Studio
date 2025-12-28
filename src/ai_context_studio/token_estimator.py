# -*- coding: utf-8 -*-
"""
Professional Token Estimation and Cost Calculation Engine.

This module provides utilities for:
- Precise token counting with content-aware estimation
- Financial cost calculations with multi-currency support
- Model registry with up-to-date Gemini pricing
- Historical cost tracking for accuracy refinement

Author: Giancarlo Allegretti
Version: 2.0.0
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .constants import CONFIG_DIR

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class Currency(Enum):
    """Supported currencies for cost calculation."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"

    @property
    def symbol(self) -> str:
        """Get currency symbol."""
        symbols = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
        return symbols.get(self.value, "$")


class ContentType(Enum):
    """Content types for optimized token estimation."""
    CODE = "code"
    PROSE_EN = "prose_en"
    PROSE_IT = "prose_it"
    MIXED = "mixed"
    JSON = "json"
    MARKDOWN = "markdown"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ModelPricing:
    """
    Pricing information for a specific AI model.
    All prices are in USD per 1 million tokens.
    """
    model_id: str
    display_name: str
    input_price_per_million: float
    output_price_per_million: float
    context_window: int
    is_active: bool = True

    @property
    def input_price_per_token(self) -> float:
        """Price per single input token in USD."""
        return self.input_price_per_million / 1_000_000

    @property
    def output_price_per_token(self) -> float:
        """Price per single output token in USD."""
        return self.output_price_per_million / 1_000_000


@dataclass
class CostEstimate:
    """Result of a cost estimation calculation."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    currency: Currency
    model_id: str
    model_name: str
    content_type: ContentType
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "input_cost": round(self.input_cost, 6),
            "output_cost": round(self.output_cost, 6),
            "total_cost": round(self.total_cost, 6),
            "currency": self.currency.value,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "content_type": self.content_type.value,
            "timestamp": self.timestamp,
        }

    def format_cost(self, value: Optional[float] = None) -> str:
        """Format a cost value for display."""
        cost = value if value is not None else self.total_cost
        symbol = self.currency.symbol

        if cost < 0.01:
            return f"{symbol}{cost:.4f}"
        elif cost < 1:
            return f"{symbol}{cost:.3f}"
        else:
            return f"{symbol}{cost:.2f}"


@dataclass
class CostHistoryEntry:
    """A single entry in the cost history log."""
    timestamp: str
    model_id: str
    estimated_tokens: int
    actual_tokens: Optional[int]
    estimated_cost: float
    actual_cost: Optional[float]
    currency: str
    content_type: str
    accuracy_ratio: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostHistoryEntry:
        return cls(**data)


# =============================================================================
# MODEL REGISTRY
# =============================================================================

class ModelRegistry:
    """
    Registry of AI models with pricing information.
    Prices based on Google Gemini pricing (December 2024).
    """

    DEFAULT_EXCHANGE_RATES: dict[Currency, float] = {
        Currency.USD: 1.0,
        Currency.EUR: 0.92,
        Currency.GBP: 0.79,
        Currency.JPY: 149.50,
    }

    MODELS: dict[str, ModelPricing] = {
        "gemini-2.0-flash": ModelPricing(
            model_id="gemini-2.0-flash",
            display_name="Gemini 2.0 Flash",
            input_price_per_million=0.075,
            output_price_per_million=0.30,
            context_window=1_048_576,
        ),
        "gemini-2.0-flash-exp": ModelPricing(
            model_id="gemini-2.0-flash-exp",
            display_name="Gemini 2.0 Flash Exp",
            input_price_per_million=0.0,
            output_price_per_million=0.0,
            context_window=1_048_576,
        ),
        "gemini-1.5-flash": ModelPricing(
            model_id="gemini-1.5-flash",
            display_name="Gemini 1.5 Flash",
            input_price_per_million=0.075,
            output_price_per_million=0.30,
            context_window=1_048_576,
        ),
        "gemini-1.5-flash-8b": ModelPricing(
            model_id="gemini-1.5-flash-8b",
            display_name="Gemini 1.5 Flash-8B",
            input_price_per_million=0.0375,
            output_price_per_million=0.15,
            context_window=1_048_576,
        ),
        "gemini-1.5-pro": ModelPricing(
            model_id="gemini-1.5-pro",
            display_name="Gemini 1.5 Pro",
            input_price_per_million=3.50,
            output_price_per_million=10.50,
            context_window=2_097_152,
        ),
        "gemini-2.5-flash-preview-05-20": ModelPricing(
            model_id="gemini-2.5-flash-preview-05-20",
            display_name="Gemini 2.5 Flash Preview",
            input_price_per_million=0.15,
            output_price_per_million=0.60,
            context_window=1_048_576,
        ),
        "gemini-1.0-pro": ModelPricing(
            model_id="gemini-1.0-pro",
            display_name="Gemini 1.0 Pro",
            input_price_per_million=0.50,
            output_price_per_million=1.50,
            context_window=32_768,
        ),
    }

    DEFAULT_MODEL = "gemini-1.5-flash"

    @classmethod
    def get_model(cls, model_name: str) -> ModelPricing:
        """Get pricing info for a model."""
        clean_name = model_name.replace("models/", "").lower()

        if clean_name in cls.MODELS:
            return cls.MODELS[clean_name]

        for key, model in cls.MODELS.items():
            if key in clean_name or clean_name in key:
                return model

        logger.warning("Unknown model '%s', using default", model_name)
        return cls.MODELS[cls.DEFAULT_MODEL]

    @classmethod
    def list_models(cls) -> list[ModelPricing]:
        """Get all available models."""
        return [m for m in cls.MODELS.values() if m.is_active]

    @classmethod
    def get_exchange_rate(
        cls,
        target: Currency,
        custom_rates: Optional[dict[Currency, float]] = None
    ) -> float:
        """Get exchange rate from USD to target currency."""
        rates = custom_rates or cls.DEFAULT_EXCHANGE_RATES
        return rates.get(target, 1.0)


# =============================================================================
# TOKEN ESTIMATOR
# =============================================================================

class TokenEstimator:
    """
    Advanced token estimation with content-aware heuristics.
    """

    CHAR_RATIOS: dict[ContentType, float] = {
        ContentType.CODE: 3.8,
        ContentType.PROSE_EN: 4.0,
        ContentType.PROSE_IT: 4.2,
        ContentType.MIXED: 4.0,
        ContentType.JSON: 3.5,
        ContentType.MARKDOWN: 4.0,
    }

    DEFAULT_RATIO: float = 4.0

    @classmethod
    def detect_content_type(cls, text: str) -> ContentType:
        """Auto-detect the content type of text."""
        if not text:
            return ContentType.MIXED

        sample = text[:2000]
        stripped = sample.strip()

        # Check JSON
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                json.loads(text)
                return ContentType.JSON
            except:
                pass

        # Check code patterns
        code_patterns = [
            r'def\s+\w+\s*\(', r'function\s+\w+\s*\(', r'class\s+\w+',
            r'import\s+[\w.]+', r'const\s+\w+\s*=', r'let\s+\w+\s*=',
            r'public\s+\w+\s+\w+\s*\(', r'#include\s*<', r'fn\s+\w+\s*\(',
        ]
        code_matches = sum(1 for p in code_patterns if re.search(p, sample))
        if code_matches >= 2:
            return ContentType.CODE

        # Check Markdown
        md_patterns = [r'^#+\s', r'^\*\s', r'^\d+\.\s', r'```', r'\[.*\]\(.*\)']
        md_matches = sum(1 for p in md_patterns if re.search(p, sample, re.MULTILINE))
        if md_matches >= 2:
            return ContentType.MARKDOWN

        # Check Italian
        italian_words = ['che', 'della', 'nella', 'sono', 'questo', 'perché', 'quando', 'anche']
        italian_count = sum(1 for w in italian_words if re.search(rf'\b{w}\b', sample.lower()))
        if italian_count >= 3:
            return ContentType.PROSE_IT

        return ContentType.MIXED

    @classmethod
    def estimate_tokens(cls, text: str, content_type: Optional[ContentType] = None) -> int:
        """Estimate token count for text."""
        if not text:
            return 0

        if content_type is None:
            content_type = cls.detect_content_type(text)

        ratio = cls.CHAR_RATIOS.get(content_type, cls.DEFAULT_RATIO)
        return int(len(text) / ratio)

    @classmethod
    def estimate_output_tokens(cls, input_tokens: int, multiplier: float = 1.5) -> int:
        """Estimate expected output tokens."""
        return int(input_tokens * multiplier)

    @staticmethod
    def format_token_count(tokens: int) -> str:
        """Format token count for display."""
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        elif tokens >= 1_000:
            return f"{tokens:,}"
        return str(tokens)


# =============================================================================
# COST CALCULATOR
# =============================================================================

class CostCalculator:
    """
    Professional cost calculation engine with multi-currency support.
    """

    def __init__(
        self,
        default_currency: Currency = Currency.EUR,
        custom_exchange_rates: Optional[dict[Currency, float]] = None,
        output_multiplier: float = 1.5
    ):
        self.default_currency = default_currency
        self.custom_exchange_rates = custom_exchange_rates
        self.output_multiplier = output_multiplier

    def calculate_cost(
        self,
        text: str,
        model_name: str = "gemini-1.5-flash",
        currency: Optional[Currency] = None,
        content_type: Optional[ContentType] = None,
        include_output: bool = True
    ) -> CostEstimate:
        """Calculate the estimated cost for processing text."""
        currency = currency or self.default_currency
        model = ModelRegistry.get_model(model_name)

        if content_type is None:
            content_type = TokenEstimator.detect_content_type(text)

        input_tokens = TokenEstimator.estimate_tokens(text, content_type)
        output_tokens = (
            TokenEstimator.estimate_output_tokens(input_tokens, self.output_multiplier)
            if include_output else 0
        )

        input_cost_usd = input_tokens * model.input_price_per_token
        output_cost_usd = output_tokens * model.output_price_per_token
        total_cost_usd = input_cost_usd + output_cost_usd

        exchange_rate = ModelRegistry.get_exchange_rate(currency, self.custom_exchange_rates)

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost=input_cost_usd * exchange_rate,
            output_cost=output_cost_usd * exchange_rate,
            total_cost=total_cost_usd * exchange_rate,
            currency=currency,
            model_id=model.model_id,
            model_name=model.display_name,
            content_type=content_type,
        )

    def calculate_from_tokens(
        self,
        input_tokens: int,
        model_name: str = "gemini-1.5-flash",
        currency: Optional[Currency] = None,
        include_output: bool = True
    ) -> CostEstimate:
        """Calculate cost from token count directly."""
        currency = currency or self.default_currency
        model = ModelRegistry.get_model(model_name)

        output_tokens = (
            TokenEstimator.estimate_output_tokens(input_tokens, self.output_multiplier)
            if include_output else 0
        )

        input_cost_usd = input_tokens * model.input_price_per_token
        output_cost_usd = output_tokens * model.output_price_per_token
        total_cost_usd = input_cost_usd + output_cost_usd

        exchange_rate = ModelRegistry.get_exchange_rate(currency, self.custom_exchange_rates)

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost=input_cost_usd * exchange_rate,
            output_cost=output_cost_usd * exchange_rate,
            total_cost=total_cost_usd * exchange_rate,
            currency=currency,
            model_id=model.model_id,
            model_name=model.display_name,
            content_type=ContentType.MIXED,
        )

    def compare_models(
        self,
        input_tokens: int,
        models: Optional[list[str]] = None,
        currency: Optional[Currency] = None
    ) -> list[CostEstimate]:
        """Compare costs across multiple models."""
        if models is None:
            models = [m.model_id for m in ModelRegistry.list_models()]

        estimates = [
            self.calculate_from_tokens(input_tokens, model, currency)
            for model in models
        ]

        return sorted(estimates, key=lambda e: e.total_cost)


# =============================================================================
# COST HISTORY MANAGER
# =============================================================================

class CostHistoryManager:
    """Manages historical cost data for tracking and accuracy refinement."""

    HISTORY_FILE = CONFIG_DIR / "cost_history.json"
    MAX_ENTRIES = 1000

    def __init__(self):
        self._history: list[CostHistoryEntry] = []
        self._load()

    def _load(self) -> None:
        """Load history from file."""
        if self.HISTORY_FILE.exists():
            try:
                with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._history = [
                        CostHistoryEntry.from_dict(entry)
                        for entry in data.get('entries', [])
                    ]
            except Exception as e:
                logger.error("Failed to load cost history: %s", e)
                self._history = []

    def _save(self) -> None:
        """Save history to file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            entries = self._history[-self.MAX_ENTRIES:]
            with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump({"entries": [e.to_dict() for e in entries]}, f, indent=2)
        except Exception as e:
            logger.error("Failed to save cost history: %s", e)

    def add_entry(
        self,
        estimate: CostEstimate,
        actual_tokens: Optional[int] = None,
        actual_cost: Optional[float] = None
    ) -> None:
        """Add a new entry to history."""
        accuracy_ratio = None
        if actual_tokens and estimate.total_tokens > 0:
            accuracy_ratio = actual_tokens / estimate.total_tokens

        entry = CostHistoryEntry(
            timestamp=estimate.timestamp,
            model_id=estimate.model_id,
            estimated_tokens=estimate.total_tokens,
            actual_tokens=actual_tokens,
            estimated_cost=estimate.total_cost,
            actual_cost=actual_cost,
            currency=estimate.currency.value,
            content_type=estimate.content_type.value,
            accuracy_ratio=accuracy_ratio,
        )

        self._history.append(entry)
        self._save()

    def get_entries(self, limit: int = 100) -> list[CostHistoryEntry]:
        """Get recent history entries."""
        return self._history[-limit:]

    def get_total_spend(self, currency: str = "EUR", days: int = 30) -> float:
        """Get total spend over a period."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        total = 0.0
        for entry in self._history:
            if entry.timestamp >= cutoff and entry.currency == currency:
                if entry.actual_cost is not None:
                    total += entry.actual_cost
                else:
                    total += entry.estimated_cost
        return total

    def get_accuracy_stats(self, model_id: Optional[str] = None) -> dict[str, float]:
        """Get accuracy statistics."""
        entries = [
            e for e in self._history
            if e.accuracy_ratio is not None
            and (model_id is None or e.model_id == model_id)
        ]

        if not entries:
            return {"average": 1.0, "min": 1.0, "max": 1.0, "count": 0}

        ratios = [e.accuracy_ratio for e in entries]
        return {
            "average": sum(ratios) / len(ratios),
            "min": min(ratios),
            "max": max(ratios),
            "count": len(ratios),
        }

    def clear(self) -> None:
        """Clear all history."""
        self._history = []
        self._save()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_calculator: Optional[CostCalculator] = None


def get_calculator(currency: Currency = Currency.EUR) -> CostCalculator:
    """Get a calculator instance."""
    global _default_calculator
    if _default_calculator is None or _default_calculator.default_currency != currency:
        _default_calculator = CostCalculator(default_currency=currency)
    return _default_calculator


def estimate_cost(
    text: str,
    model: str = "gemini-1.5-flash",
    currency: str = "EUR"
) -> CostEstimate:
    """Quick cost estimation."""
    calc = CostCalculator(default_currency=Currency[currency.upper()])
    return calc.calculate_cost(text, model)


def estimate_cost_from_tokens(
    tokens: int,
    model: str = "gemini-1.5-flash",
    currency: str = "EUR"
) -> CostEstimate:
    """Quick cost estimation from token count."""
    calc = CostCalculator(default_currency=Currency[currency.upper()])
    return calc.calculate_from_tokens(tokens, model)

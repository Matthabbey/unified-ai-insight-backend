"""
Atlas — Semantic Kernel Setup
Initialises the kernel with all agents registered as plugins.
Only used when Semantic Kernel is installed and Azure OpenAI is configured.
"""
import os
import logging
from typing import Optional

try:
    from semantic_kernel import Kernel
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureTextEmbedding
    SK_AVAILABLE = True
except ImportError:
    Kernel = object  # type: ignore[assignment,misc]
    AzureChatCompletion = None  # type: ignore[assignment]
    AzureTextEmbedding = None  # type: ignore[assignment]
    SK_AVAILABLE = False

logger = logging.getLogger(__name__)

_kernel_instance: Optional[object] = None


def build_kernel():
    """
    Build and return a configured Semantic Kernel instance
    with Azure OpenAI services attached.
    Returns None gracefully if SK is not installed.
    """
    if not SK_AVAILABLE:
        logger.warning("Semantic Kernel not installed — kernel unavailable.")
        return None

    kernel = Kernel()

    # ── GPT-4o for complex reasoning (Strategist, Scribe) ──────────────────
    kernel.add_service(
        AzureChatCompletion(
            service_id="gpt4o",
            deployment_name=os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-4o"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        )
    )

    # ── GPT-5.4-nano for fast queries (Researcher, Analyst, Watchdog) ──────
    kernel.add_service(
        AzureChatCompletion(
            service_id="nano",
            deployment_name=os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT", "gpt-5.4-nano"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        )
    )

    # ── Embeddings for semantic memory ─────────────────────────────────────
    kernel.add_service(
        AzureTextEmbedding(
            service_id="embeddings",
            deployment_name="text-embedding-ada-002",
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
    )

    logger.info("Semantic Kernel built with GPT-4o, nano, and embeddings.")
    return kernel


def get_kernel():
    """Return the singleton kernel instance, building it on first call."""
    global _kernel_instance
    if _kernel_instance is None:
        _kernel_instance = build_kernel()
        if _kernel_instance is not None:
            _register_agents(_kernel_instance)
    return _kernel_instance


def _register_agents(kernel):
    """Register all agent plugins with the kernel."""
    from agents.researcher import ResearcherAgent
    from agents.analyst import AnalystAgent
    from agents.watchdog import WatchdogAgent
    from agents.scribe import ScribeAgent
    from agents.strategist import StrategistAgent

    kernel.add_plugin(ResearcherAgent(), plugin_name="Researcher")
    kernel.add_plugin(AnalystAgent(), plugin_name="Analyst")
    kernel.add_plugin(WatchdogAgent(), plugin_name="Watchdog")
    kernel.add_plugin(ScribeAgent(), plugin_name="Scribe")
    kernel.add_plugin(StrategistAgent(kernel), plugin_name="Strategist")

    logger.info("All 5 agents registered with kernel.")

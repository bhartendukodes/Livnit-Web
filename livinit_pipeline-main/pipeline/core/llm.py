import os
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def extract_reasoning_trace(response) -> tuple[str | None, str | None]:
    """Extract reasoning trace and final answer from a Gemini response with thinking enabled.

    Returns:
        tuple: (reasoning_trace, final_answer) - either may be None if not present
    """
    reasoning_trace = None
    final_answer = None

    try:
        for part in response.candidates[0].content.parts:
            if part.thought:
                reasoning_trace = part.text
            elif part.text:
                final_answer = part.text
    except (AttributeError, IndexError):
        # Fallback if response structure is different
        final_answer = getattr(response, "text", None)

    return reasoning_trace, final_answer


def log_reasoning_trace(stage: str, reasoning_trace: str | None, manager=None, filename: str = "reasoning_trace.txt") -> None:
    """Log and optionally save the reasoning trace for a stage.

    Args:
        stage: The stage name for logging
        reasoning_trace: The reasoning text to log
        manager: Optional AssetManager to save trace to file
        filename: Filename for saving (default: reasoning_trace.txt)
    """
    if reasoning_trace:
        logger.info("[%s] --- REASONING TRACE ---", stage)
        for line in reasoning_trace.split("\n"):
            logger.info("[%s] %s", stage, line)
        logger.info("[%s] --- END REASONING TRACE ---", stage)

        if manager is not None:
            manager.write_text(stage, filename, reasoning_trace)

ASSET_SELECTOR_CONFIG = types.GenerateContentConfig(
    temperature=1.0,
    response_mime_type="application/json",
    thinking_config=types.ThinkingConfig(thinking_budget=2048, include_thoughts=True),
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

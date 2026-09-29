"""The single place where the app talks to a language model.

Every model call in this project goes through generate(). To switch to a
different provider later, only this file needs to change.
"""

import os
import time

from dotenv import load_dotenv

# Read GEMINI_API_KEY (and optional GEMINI_MODEL) from the .env file.
load_dotenv()

# Default free-tier model. Can be overridden with GEMINI_MODEL in .env.
DEFAULT_MODEL = "gemini-3.8-flash"

# Lighter model tried once if the main model is still busy (503) after retries.
FALLBACK_MODEL = "gemini-3.5-flash-lite"

# Seconds to wait before each retry of a temporary 503 error (so 2 retries).
# Quota errors (429) are never retried: retrying only uses up more quota.
RETRY_DELAYS = [2, 4]

QUOTA_MESSAGE = "Free usage limit reached, please wait and try again."
BUSY_MESSAGE = "The AI service is busy right now. Please wait a moment and try again."


class MissingAPIKeyError(Exception):
    """Raised when no Gemini API key has been set in .env."""


class LLMError(Exception):
    """Raised when the model call fails (bad key, rate limit, network, ...)."""


class QuotaError(LLMError):
    """Raised when the free-tier quota is used up (429 / RESOURCE_EXHAUSTED)."""


def _is_quota_error(e):
    return getattr(e, "code", None) == 429 or getattr(e, "status", None) == "RESOURCE_EXHAUSTED"


def _is_temporary_error(e):
    return getattr(e, "code", None) == 503


def get_api_key():
    """Return the API key, or raise MissingAPIKeyError if it is not set."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise MissingAPIKeyError(
            "No Gemini API key found. Open the .env file in the project folder "
            "and paste your key after GEMINI_API_KEY=, then restart the app."
        )
    return key


def generate(system_prompt, messages, json_output=False):
    """Send a conversation to the model and return its reply as text.

    system_prompt: instructions for the model (loaded from /prompts).
    messages: list of {"role": "user" | "assistant", "content": str}.
    json_output: if True, ask the model to reply with JSON only (used by the judge).
    """
    api_key = get_api_key()

    # Imported here so a missing key is reported before any library setup.
    from google import genai
    from google.genai import types

    # Gemini calls the assistant role "model".
    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json" if json_output else None,
    )

    def call(model):
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        return response.text or ""

    return _with_retry(call, os.getenv("GEMINI_MODEL", DEFAULT_MODEL))


def _raise_unless_busy(e):
    """Turn any error other than a temporary 503 into the right LLMError."""
    if _is_quota_error(e):
        raise QuotaError(QUOTA_MESSAGE) from e
    if not _is_temporary_error(e):
        raise LLMError(f"The Gemini API call failed: {e}") from e


def _with_retry(call, model, fallback=FALLBACK_MODEL):
    """Run call(model), handling errors:

    - 503 (busy): retry the main model, then try the fallback model once.
    - 429 (quota): never retried, never sent to the fallback.
    - anything else: fail once.
    """
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return call(model)
        except Exception as e:
            _raise_unless_busy(e)
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])

    # Main model still busy after all retries: one attempt on the lighter model.
    if fallback and fallback != model:
        try:
            return call(fallback)
        except Exception as e:
            _raise_unless_busy(e)

    raise LLMError(BUSY_MESSAGE)

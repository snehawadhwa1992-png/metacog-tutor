"""The single place where the app talks to a language model.

Every model call in this project goes through generate(). To switch to a
different provider later, only this file needs to change.
"""

import os

from dotenv import load_dotenv

# Read GEMINI_API_KEY (and optional GEMINI_MODEL) from the .env file.
load_dotenv()

# Default free-tier model. Can be overridden with GEMINI_MODEL in .env.
DEFAULT_MODEL = "gemini-2.5-flash"


class MissingAPIKeyError(Exception):
    """Raised when no Gemini API key has been set in .env."""


class LLMError(Exception):
    """Raised when the model call fails (bad key, rate limit, network, ...)."""


def get_api_key():
    """Return the API key, or raise MissingAPIKeyError if it is not set."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise MissingAPIKeyError(
            "No Gemini API key found. Open the .env file in the project folder "
            "and paste your key after GEMINI_API_KEY=, then restart the app."
        )
    return key


def generate(system_prompt, messages):
    """Send a conversation to the model and return its reply as text.

    system_prompt: instructions for the model (loaded from /prompts).
    messages: list of {"role": "user" | "assistant", "content": str}.
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

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
    except Exception as e:
        raise LLMError(f"The Gemini API call failed: {e}") from e

    return response.text or ""

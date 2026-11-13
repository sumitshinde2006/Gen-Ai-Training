"""Provider-neutral text generation for KandaGuide."""

import os
from typing import Tuple

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-20b",
    "gemini": "gemini-3.5-flash-lite",
}
REQUEST_TIMEOUT_SECONDS = 30


class LLMError(RuntimeError):
    """Base error for safe, user-facing LLM failures."""


class LLMConfigurationError(LLMError):
    """Raised when provider configuration is missing or invalid."""


class LLMProviderError(LLMError):
    """Raised when a configured provider cannot generate a response."""


def _provider_config() -> Tuple[str, str, str]:
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider not in DEFAULT_MODELS:
        raise LLMConfigurationError(
            "Invalid LLM_PROVIDER. Choose 'groq' or 'gemini'."
        )

    key_variable = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
    api_key = os.getenv(key_variable, "").strip()
    if not api_key:
        raise LLMConfigurationError(
            f"{key_variable} is not configured."
        )

    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS[provider]
    return provider, api_key, model


def _generate_with_groq(
    api_key: str, model: str, system_prompt: str, user_prompt: str
) -> str:
    try:
        from groq import APITimeoutError, APIError, Groq
    except ImportError as error:
        raise LLMConfigurationError(
            "The Groq SDK is unavailable. Install project requirements."
        ) from error

    try:
        client = Groq(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except APITimeoutError:
        raise LLMProviderError("The Groq request timed out.") from None
    except APIError:
        raise LLMProviderError("The Groq provider could not complete the request.") from None

    if not response.choices:
        raise LLMProviderError("The Groq provider returned an empty response.")

    content = response.choices[0].message.content
    if not content:
        raise LLMProviderError("The Groq provider returned an empty response.")
    return content


def _generate_with_gemini(
    api_key: str, model: str, system_prompt: str, user_prompt: str
) -> str:
    try:
        from google import genai
        from google.genai import errors, types
        import httpx2
    except ImportError as error:
        raise LLMConfigurationError(
            "The Google GenAI SDK is unavailable. Install project requirements."
        ) from error

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=REQUEST_TIMEOUT_SECONDS * 1000
            ),
        )
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
    except httpx2.TimeoutException:
        raise LLMProviderError("The Gemini request timed out.") from None
    except httpx2.HTTPError:
        raise LLMProviderError(
            "The Gemini provider could not complete the request."
        ) from None
    except errors.APIError:
        raise LLMProviderError(
            "The Gemini provider could not complete the request."
        ) from None

    if not response.text:
        raise LLMProviderError("The Gemini provider returned an empty response.")
    return response.text


def generate_response(system_prompt: str, user_prompt: str) -> str:
    """Generate a response using the configured Groq or Gemini provider."""
    provider, api_key, model = _provider_config()

    if provider == "groq":
        return _generate_with_groq(api_key, model, system_prompt, user_prompt)
    return _generate_with_gemini(api_key, model, system_prompt, user_prompt)

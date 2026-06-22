import os
import json
import time
import logging
from openai import AzureOpenAI
from .azure_llm_service import _load_config_from_vault, build_llm_config  # Adjust path if needed


def evaluate_with_azure_llm(
        prompt: str,
        cache_path: str,
        max_retries: int = 3,
        backoff_factor: int = 2,
        request_timeout: int = 30,
        logger=None
) -> dict:
    _log = logger or logging

    # Load Azure OpenAI credentials and config from Key Vault
    llm_config = build_llm_config(temperature=0)  # Or set temperature as needed

    model = llm_config['model']
    api_key = llm_config['api_key']
    endpoint = llm_config['endpoint']
    api_version = llm_config['api_version']

    # Initialize Azure OpenAI client
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        base_url=f"{endpoint}/openai/deployments/{model}"
    )

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=llm_config.get('temperature', 0),
                timeout=request_timeout,
                messages=[
                    {"role": "system", "content": (
                        "You are a precise data extraction agent. "
                        "Always return ONLY valid JSON, no explanations, no markdown, no extra text."
                    )},
                    {"role": "user", "content": prompt},
                ],
            )

            raw = response.choices[0].message.content.strip()
            print("\n[DEBUG] Raw LLM response:\n", raw, "\n")  # <--- Debug print

            # Robustly strip markdown and whitespace
            if raw.startswith("```json"):
                raw = raw[len("```json"):].strip()
            if raw.startswith("```"):
                raw = raw[3:].strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()

            # Save to cache
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(raw)

            # Try parsing JSON
            try:
                return json.loads(raw)
            except json.JSONDecodeError as jde:
                _log.warning("JSON decode error: %s\nRaw content: %r", jde, raw)
                # Optionally, save the raw response to a .txt file for manual inspection
                with open(cache_path + ".txt", "w", encoding="utf-8") as ftxt:
                    ftxt.write(raw)
                raise

        except Exception as e:
            wait = (backoff_factor ** attempt) + (0.25 * (attempt + 1))
            _log.warning("Azure LLM error: %s (attempt %d/%d). Retrying in %.2fs...",
                         str(e), attempt + 1, max_retries, wait)
            time.sleep(wait)

    _log.error("All retries exhausted for Azure LLM.")
    return {"answer": "[API Error: all retries exhausted]"}

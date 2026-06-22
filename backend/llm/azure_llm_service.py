import os
import logging
import time
from dotenv import load_dotenv
from typing import Dict, Any
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

load_dotenv()

logger = logging.getLogger(__name__)

KEY_VAULT_URL = "https://fstodevazureopenai.vault.azure.net/"

def _load_config_from_vault() -> Dict[str, Any]:
    """Load API key and endpoint from Azure Key Vault with retry logic"""
    kv_url = KEY_VAULT_URL
    api_key = None
    endpoint = None
    api_version = None
    model = None

    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            credential = DefaultAzureCredential()
            kvclient = SecretClient(vault_url=kv_url, credential=credential)

            try:
                api_key = kvclient.get_secret("llm-api-key").value
                logger.info(f"API Key loaded from Key Vault (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                logger.error(f"Failed to load API key from Key Vault (attempt {attempt + 1}/{max_retries}): {e}")
                raise ValueError(f"Failed to load API key from Key Vault: {e}")

            try:
                endpoint_secret = kvclient.get_secret("llm-base-endpoint")
                endpoint = endpoint_secret.value
                api_version_secret = kvclient.get_secret("llm-mini-version")
                api_version = api_version_secret.value
                model_secret = kvclient.get_secret("llm-41")
                model = model_secret.value
                logger.info("Endpoint loaded from Key Vault")
            except Exception as e:
                logger.warning(f"Failed to load endpoint from Key Vault: {e}; using default endpoint")
                endpoint = "https://stg-secureapi.hexaware.com/api/azureai"

            break

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Failed to load Azure config (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s: {e}")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Failed to load Azure config after {max_retries} attempts: {e}")
                raise ValueError(f"Failed to load API key from Key Vault after {max_retries} attempts: {e}")

    config = {
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "model": model,
    }

    if config.get("api_key"):
        logger.info(f"API Key loaded, starts with: {config['api_key'][:5]}...")
        logger.info(f"Azure OpenAI config - Model: {config['model']}, Endpoint: {config['endpoint']}")
    else:
        logger.error("Failed to load API key from Key Vault")

    return config

def build_llm_config(temperature: float = 0.3) -> Dict[str, Any]:
    """Build Azure OpenAI config using credentials from Azure Key Vault"""
    config = _load_config_from_vault()

    api_key = config.get("api_key")
    endpoint = config.get("endpoint")
    api_version = config.get("api_version")
    model = config.get("model")

    if not api_key:
        raise ValueError("Missing AZURE_OPENAI_API_KEY from Key Vault")
    if not endpoint:
        raise ValueError("Missing AZURE_OPENAI_ENDPOINT from Key Vault")

    print(f"[LLM CONFIG] Azure OpenAI | Model: {model} | Endpoint: {endpoint}")

    # Return all necessary config to use with your OpenAI/AzureOpenAI client
    return {
        "model": model,
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "temperature": temperature,
        "timeout": 180,
    }

llm_config = build_llm_config()
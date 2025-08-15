"""
Configuration management for FlowSlide AI features
"""

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load environment variables with error handling
try:
    load_dotenv()
except (PermissionError, FileNotFoundError) as e:
    # Silently continue if .env file is not accessible
    # This allows the application to work with system environment variables
    pass
except Exception as e:
    # Log other errors but continue
    import logging

    logging.getLogger(__name__).warning(f"Could not load .env file: {e}")


class AIConfig(BaseSettings):
    """AI configuration settings"""

    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-haiku-20240307"

    # Google AI Configuration
    google_api_key: Optional[str] = None
    google_model: str = "gemini-1.5-flash"

    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_name: Optional[str] = None

    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"

    # Hugging Face Configuration
    huggingface_api_token: Optional[str] = None

    # General AI Configuration
    default_ai_provider: str = "openai"
    max_tokens: int = 2000
    temperature: float = 0.7
    top_p: float = 1.0

    # Search Engine Configuration
    tavily_api_key: Optional[str] = None
    tavily_max_results: int = 10
    tavily_search_depth: str = "advanced"
    tavily_include_domains: Optional[str] = None
    tavily_exclude_domains: Optional[str] = None

    # SearXNG Configuration
    searxng_host: Optional[str] = None
    searxng_max_results: int = 10
    searxng_language: str = "en"
    searxng_timeout: int = 10

    # Research Configuration
    research_provider: str = "tavily"
    research_enable_content_extraction: bool = True
    research_max_content_length: int = 50000
    research_extraction_timeout: int = 30

    # Apryse Configuration
    apryse_license_key: Optional[str] = None

    model_config = {"case_sensitive": False, "extra": "ignore"}


# Global AI configuration instance
ai_config = AIConfig()


def reload_ai_config():
    """Reload AI configuration from environment variables"""
    global ai_config
    # Force reload environment variables with error handling
    import os

    from dotenv import load_dotenv

    env_file = os.path.join(os.getcwd(), ".env")
    try:
        load_dotenv(env_file, override=True)
    except (PermissionError, FileNotFoundError) as e:
        # Silently continue if .env file is not accessible
        pass
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Could not reload .env file: {e}")

    # Force update the existing instance with new values from environment
    ai_config.openai_model = os.environ.get("OPENAI_MODEL", ai_config.openai_model)
    ai_config.openai_base_url = os.environ.get(
        "OPENAI_BASE_URL", ai_config.openai_base_url
    )
    ai_config.openai_api_key = os.environ.get(
        "OPENAI_API_KEY", ai_config.openai_api_key
    )
    ai_config.anthropic_api_key = os.environ.get(
        "ANTHROPIC_API_KEY", ai_config.anthropic_api_key
    )
    ai_config.anthropic_model = os.environ.get(
        "ANTHROPIC_MODEL", ai_config.anthropic_model
    )
    ai_config.google_api_key = os.environ.get(
        "GOOGLE_API_KEY", ai_config.google_api_key
    )
    ai_config.google_model = os.environ.get("GOOGLE_MODEL", ai_config.google_model)
    ai_config.default_ai_provider = os.environ.get(
        "DEFAULT_AI_PROVIDER", ai_config.default_ai_provider
    )
    ai_config.max_tokens = int(os.environ.get("MAX_TOKENS", str(ai_config.max_tokens)))
    ai_config.temperature = float(
        os.environ.get("TEMPERATURE", str(ai_config.temperature))
    )
    ai_config.top_p = float(os.environ.get("TOP_P", str(ai_config.top_p)))

    # Update Tavily configuration
    ai_config.tavily_api_key = os.environ.get(
        "TAVILY_API_KEY", ai_config.tavily_api_key
    )
    ai_config.tavily_max_results = int(
        os.environ.get("TAVILY_MAX_RESULTS", str(ai_config.tavily_max_results))
    )
    ai_config.tavily_search_depth = os.environ.get(
        "TAVILY_SEARCH_DEPTH", ai_config.tavily_search_depth
    )
    ai_config.tavily_include_domains = os.environ.get(
        "TAVILY_INCLUDE_DOMAINS", ai_config.tavily_include_domains
    )
    ai_config.tavily_exclude_domains = os.environ.get(
        "TAVILY_EXCLUDE_DOMAINS", ai_config.tavily_exclude_domains
    )

    # Update SearXNG configuration
    ai_config.searxng_host = os.environ.get("SEARXNG_HOST", ai_config.searxng_host)
    ai_config.searxng_max_results = int(
        os.environ.get("SEARXNG_MAX_RESULTS", str(ai_config.searxng_max_results))
    )
    ai_config.searxng_language = os.environ.get(
        "SEARXNG_LANGUAGE", ai_config.searxng_language
    )
    ai_config.searxng_timeout = int(
        os.environ.get("SEARXNG_TIMEOUT", str(ai_config.searxng_timeout))
    )

    # Update Research configuration
    ai_config.research_provider = os.environ.get(
        "RESEARCH_PROVIDER", ai_config.research_provider
    )
    ai_config.research_enable_content_extraction = (
        os.environ.get(
            "RESEARCH_ENABLE_CONTENT_EXTRACTION",
            str(ai_config.research_enable_content_extraction),
        ).lower()
        == "true"
    )
    ai_config.research_max_content_length = int(
        os.environ.get(
            "RESEARCH_MAX_CONTENT_LENGTH", str(ai_config.research_max_content_length)
        )
    )
    ai_config.research_extraction_timeout = int(
        os.environ.get(
            "RESEARCH_EXTRACTION_TIMEOUT", str(ai_config.research_extraction_timeout)
        )
    )

    ai_config.apryse_license_key = os.environ.get(
        "APRYSE_LICENSE_KEY", ai_config.apryse_license_key
    )


class AppConfig(BaseSettings):
    """Application configuration"""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    reload: bool = True

    # Database Configuration (for future use)
    database_url: str = "sqlite:///app/db/flowslide.db"

    # Security Configuration
    secret_key: str = "your-secret-key-here"
    access_token_expire_minutes: int = 30

    # File Upload Configuration
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    upload_dir: str = "uploads"

    # Cache Configuration
    cache_ttl: int = 3600  # 1 hour

    model_config = {"case_sensitive": False, "extra": "ignore", "env_prefix": ""}


# Global app configuration instance
app_config = AppConfig()

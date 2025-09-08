"""
Configuration management for FlowSlide AI features
"""

from typing import Any, Dict, Optional

from dotenv import load_dotenv
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
    # OpenAI timeout and retry defaults (seconds / attempts)
    openai_request_timeout: int = 30
    openai_max_retries: int = 3

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-haiku-20240307"
    # Anthropic timeout and retry defaults (seconds / attempts)
    anthropic_request_timeout: int = 30
    anthropic_max_retries: int = 3

    # Google AI Configuration
    google_api_key: Optional[str] = None
    google_base_url: str = "https://generativelanguage.googleapis.com"
    google_model: str = "gemini-1.5-flash"
    # Google timeout and retry defaults (seconds / attempts)
    google_request_timeout: int = 60
    google_max_retries: int = 3

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

    # Helper methods (parity with SimpleAIConfig)
    def get_available_providers(self):
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.google_api_key:
            providers.append("google")
        if self.azure_openai_api_key and self.azure_openai_endpoint:
            providers.append("azure_openai")
        providers.append("ollama")
        return providers or ["openai"]

    def is_provider_available(self, provider: str) -> bool:
        return provider in self.get_available_providers()

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        provider = (provider or "").lower()
        if provider == "openai":
            return {
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url,
                "model": self.openai_model,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
                "request_timeout": self.openai_request_timeout,
                "max_retries": self.openai_max_retries,
            }
        if provider == "anthropic":
            return {
                "api_key": self.anthropic_api_key,
                "base_url": self.anthropic_base_url,
                "model": self.anthropic_model,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
                "request_timeout": self.anthropic_request_timeout,
                "max_retries": self.anthropic_max_retries,
            }
        if provider in ("google", "gemini"):
            return {
                "api_key": self.google_api_key,
                "base_url": self.google_base_url,
                "model": self.google_model,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
                "request_timeout": self.google_request_timeout,
                "max_retries": self.google_max_retries,
            }
        if provider == "azure_openai":
            return {
                "api_key": self.azure_openai_api_key,
                "endpoint": self.azure_openai_endpoint,
                "api_version": self.azure_openai_api_version,
                "deployment_name": self.azure_openai_deployment_name,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
            }
        if provider == "ollama":
            return {
                "base_url": self.ollama_base_url,
                "model": self.ollama_model,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
            }
        # Default: return minimal
        return {
            "model": self.openai_model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }


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
    ai_config.openai_base_url = os.environ.get("OPENAI_BASE_URL", ai_config.openai_base_url)
    ai_config.openai_api_key = os.environ.get("OPENAI_API_KEY", ai_config.openai_api_key)
    ai_config.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", ai_config.anthropic_api_key)
    ai_config.anthropic_base_url = os.environ.get(
        "ANTHROPIC_BASE_URL", ai_config.anthropic_base_url
    )
    ai_config.anthropic_model = os.environ.get("ANTHROPIC_MODEL", ai_config.anthropic_model)
    ai_config.google_api_key = os.environ.get("GOOGLE_API_KEY", ai_config.google_api_key)
    ai_config.google_base_url = os.environ.get("GOOGLE_BASE_URL", ai_config.google_base_url)
    ai_config.google_model = os.environ.get("GOOGLE_MODEL", ai_config.google_model)
    ai_config.default_ai_provider = os.environ.get(
        "DEFAULT_AI_PROVIDER", ai_config.default_ai_provider
    )
    ai_config.max_tokens = int(os.environ.get("MAX_TOKENS", str(ai_config.max_tokens)))
    ai_config.temperature = float(os.environ.get("TEMPERATURE", str(ai_config.temperature)))
    ai_config.top_p = float(os.environ.get("TOP_P", str(ai_config.top_p)))

    # Update Tavily configuration
    ai_config.tavily_api_key = os.environ.get("TAVILY_API_KEY", ai_config.tavily_api_key)
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
    ai_config.searxng_language = os.environ.get("SEARXNG_LANGUAGE", ai_config.searxng_language)
    ai_config.searxng_timeout = int(
        os.environ.get("SEARXNG_TIMEOUT", str(ai_config.searxng_timeout))
    )

    # Update Research configuration
    ai_config.research_provider = os.environ.get("RESEARCH_PROVIDER", ai_config.research_provider)
    ai_config.research_enable_content_extraction = (
        os.environ.get(
            "RESEARCH_ENABLE_CONTENT_EXTRACTION",
            str(ai_config.research_enable_content_extraction),
        ).lower()
        == "true"
    )
    ai_config.research_max_content_length = int(
        os.environ.get("RESEARCH_MAX_CONTENT_LENGTH", str(ai_config.research_max_content_length))
    )
    ai_config.research_extraction_timeout = int(
        os.environ.get("RESEARCH_EXTRACTION_TIMEOUT", str(ai_config.research_extraction_timeout))
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

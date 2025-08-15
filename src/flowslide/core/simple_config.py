"""
向后兼容的配置文件 - 修复数据库问题同时保持所有功能
"""

import os
from typing import Optional

# 数据库配置 - 本地开发使用相对路径
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/flowslide.db")

# 异步数据库URL配置
def get_async_database_url(sync_url: str) -> str:
    """将同步数据库URL转换为异步版本，并清理不兼容的参数"""
    # 移除asyncpg不支持的参数
    url = sync_url
    if "sslmode=" in url:
        # 移除sslmode参数，因为asyncpg不支持
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        # 移除sslmode参数
        if 'sslmode' in query_params:
            del query_params['sslmode']
        # 重新构造URL
        """
        Backward-compatible simple config used across the app. Keeps DB settings and AI provider options.
        """
        import os
        from typing import Optional

        # Database config
        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/flowslide.db")


        def get_async_database_url(sync_url: str) -> str:
            """Convert sync DB URL to async and strip unsupported params for async drivers."""
            url = sync_url
            if "sslmode=" in url:
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                q = urllib.parse.parse_qs(parsed.query)
                q.pop("sslmode", None)
                new_query = urllib.parse.urlencode(q, doseq=True)
                url = urllib.parse.urlunparse(
                    (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
                )
            if url.startswith("sqlite///"):
                return url.replace("sqlite:///", "sqlite+aiosqlite:///")
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://")
            if url.startswith("mysql://"):
                return url.replace("mysql://", "mysql+aiomysql://")
            return "sqlite+aiosqlite:///./data/flowslide.db"


        ASYNC_DATABASE_URL = get_async_database_url(DATABASE_URL)


        class SimpleConfig:
            def __init__(self) -> None:
                # Core
                self.database_url = DATABASE_URL
                self.host = os.getenv("HOST", "0.0.0.0")
                self.port = int(os.getenv("PORT", "8000"))
                self.debug = os.getenv("DEBUG", "True").lower() == "true"
                self.reload = os.getenv("RELOAD", "True").lower() == "true"

                # Security
                self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here")
                self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

                # Uploads
                max_file_size_env = os.getenv("MAX_FILE_SIZE")
                if max_file_size_env is not None:
                    self.max_file_size = int(max_file_size_env)
                else:
                    mb_val = os.getenv("MAX_UPLOAD_SIZE") or os.getenv("MAX_FILE_SIZE_MB")
                    try:
                        self.max_file_size = int(mb_val) * 1024 * 1024 if mb_val is not None else 10 * 1024 * 1024
                    except ValueError:
                        self.max_file_size = 10 * 1024 * 1024
                self.upload_dir = os.getenv("UPLOAD_DIR", "uploads")

                # Cache
                self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))

                # Admin bootstrap
                admin_name = os.getenv("ADMIN_NAME") or os.getenv("ADMIN_USERNAME")
                self.admin_username = admin_name if admin_name else "admin"
                self.admin_password = os.getenv("ADMIN_PASSWORD", "admin123456")
                self.admin_email: Optional[str] = os.getenv("ADMIN_EMAIL")

                # CAPTCHA
                self.turnstile_site_key: Optional[str] = os.getenv("TURNSTILE_SITE_KEY")
                self.turnstile_secret_key: Optional[str] = os.getenv("TURNSTILE_SECRET_KEY")
                self.hcaptcha_site_key: Optional[str] = os.getenv("HCAPTCHA_SITE_KEY")
                self.hcaptcha_secret_key: Optional[str] = os.getenv("HCAPTCHA_SECRET_KEY")
                self.enable_login_captcha = os.getenv("ENABLE_LOGIN_CAPTCHA", "false").lower() == "true"


        class SimpleAIConfig:
            def __init__(self) -> None:
                # OpenAI
                self.openai_api_key = os.getenv("OPENAI_API_KEY")
                self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                self.openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

                # Anthropic
                self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
                self.anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
                self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

                # Google
                self.google_api_key = os.getenv("GOOGLE_API_KEY")
                self.google_base_url = os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com")
                self.google_model = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")

                # Azure OpenAI
                self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
                self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                self.azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
                self.azure_openai_deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

                # Ollama
                self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                self.ollama_model = os.getenv("OLLAMA_MODEL", "llama2")

                # Hugging Face
                self.huggingface_api_token = os.getenv("HUGGINGFACE_API_TOKEN")

                # Research
                self.tavily_api_key = os.getenv("TAVILY_API_KEY")
                self.tavily_max_results = int(os.getenv("TAVILY_MAX_RESULTS", "10"))
                self.tavily_search_depth = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
                self.tavily_include_domains = os.getenv("TAVILY_INCLUDE_DOMAINS")
                self.tavily_exclude_domains = os.getenv("TAVILY_EXCLUDE_DOMAINS")

                # SearXNG
                self.searxng_host = os.getenv("SEARXNG_HOST")
                self.searxng_max_results = int(os.getenv("SEARXNG_MAX_RESULTS", "10"))
                self.searxng_language = os.getenv("SEARXNG_LANGUAGE", "auto")
                self.searxng_timeout = int(os.getenv("SEARXNG_TIMEOUT", "10"))

                # General AI settings
                self.default_ai_provider = os.getenv("DEFAULT_AI_PROVIDER", "openai")
                self.max_tokens = int(os.getenv("MAX_TOKENS", "4000"))
                self.temperature = float(os.getenv("TEMPERATURE", "0.7"))
                self.enable_context_memory = os.getenv("ENABLE_CONTEXT_MEMORY", "True").lower() == "true"
                self.context_memory_size = int(os.getenv("CONTEXT_MEMORY_SIZE", "10"))
                self.enable_streaming = os.getenv("ENABLE_STREAMING", "False").lower() == "true"
                self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "60"))
                self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
                self.retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))

            def get_available_providers(self):
                providers = []
                if self.openai_api_key:
                    providers.append("openai")
                if self.anthropic_api_key:
                    providers.append("anthropic")
                if self.google_api_key:
                    providers.append("google")
                if self.azure_openai_api_key and self.azure_openai_endpoint:
                    providers.append("azure")
                providers.append("ollama")
                return providers or ["openai"]

            def is_provider_available(self, provider: str) -> bool:
                return provider in self.get_available_providers()


        # Global instances
        app_config = SimpleConfig()
ai_config = SimpleAIConfig()

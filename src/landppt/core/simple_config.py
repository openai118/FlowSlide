"""
向后兼容的配置文件 - 修复数据库问题同时保持所有功能
"""

import os
from typing import Optional

# 数据库配置 - 使用安全的Docker路径
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/db/landppt.db")

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
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        url = urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
    
    if url.startswith("sqlite:///"):
        # SQLite异步URL
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif url.startswith("postgresql://"):
        # PostgreSQL异步URL
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("mysql://"):
        # MySQL异步URL  
        return url.replace("mysql://", "mysql+aiomysql://")
    else:
        # 默认返回SQLite异步格式
        return "sqlite+aiosqlite:///app/db/landppt.db"

ASYNC_DATABASE_URL = get_async_database_url(DATABASE_URL)

# 基础应用配置
class SimpleConfig:
    def __init__(self):
        self.database_url = DATABASE_URL
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.debug = os.getenv("DEBUG", "True").lower() == "true"
        self.reload = os.getenv("RELOAD", "True").lower() == "true"
        
        # 安全配置
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        
        # 文件上传配置
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10MB
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads")
        
        # 缓存配置
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour

# 完整的AI配置类 - 包含所有原始功能
class SimpleAIConfig:
    def __init__(self):
        # OpenAI配置
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        
        # Anthropic配置
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        
        # Google AI配置
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_model = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
        
        # Azure OpenAI配置
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.azure_openai_deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        # Ollama配置
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama2")
        
        # Hugging Face配置
        self.huggingface_api_token = os.getenv("HUGGINGFACE_API_TOKEN")
        
        # 搜索引擎配置
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.tavily_max_results = int(os.getenv("TAVILY_MAX_RESULTS", "10"))
        self.tavily_search_depth = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
        self.tavily_include_domains = os.getenv("TAVILY_INCLUDE_DOMAINS")
        self.tavily_exclude_domains = os.getenv("TAVILY_EXCLUDE_DOMAINS")
        
        # SearXNG配置
        self.searxng_host = os.getenv("SEARXNG_HOST")
        self.searxng_max_results = int(os.getenv("SEARXNG_MAX_RESULTS", "10"))
        self.searxng_language = os.getenv("SEARXNG_LANGUAGE", "auto")
        self.searxng_timeout = int(os.getenv("SEARXNG_TIMEOUT", "10"))
        
        # 研究功能配置
        self.research_provider = os.getenv("RESEARCH_PROVIDER", "tavily")
        self.research_enable_content_extraction = os.getenv("RESEARCH_ENABLE_CONTENT_EXTRACTION", "True").lower() == "true"
        self.research_max_content_length = int(os.getenv("RESEARCH_MAX_CONTENT_LENGTH", "10000"))
        self.research_extraction_timeout = int(os.getenv("RESEARCH_EXTRACTION_TIMEOUT", "30"))
        
        # 通用AI配置
        self.default_ai_provider = os.getenv("DEFAULT_AI_PROVIDER", "openai")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "4000"))
        self.temperature = float(os.getenv("TEMPERATURE", "0.7"))
        
        # 模型配置
        self.enable_context_memory = os.getenv("ENABLE_CONTEXT_MEMORY", "True").lower() == "true"
        self.context_memory_size = int(os.getenv("CONTEXT_MEMORY_SIZE", "10"))
        self.enable_streaming = os.getenv("ENABLE_STREAMING", "False").lower() == "true"
        
        # 性能配置
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "60"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))
    
    def get_available_providers(self):
        """返回可用的AI提供商列表"""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.google_api_key:
            providers.append("google")
        if self.azure_openai_api_key and self.azure_openai_endpoint:
            providers.append("azure")
        providers.append("ollama")  # Ollama通常可用
        return providers or ["openai"]  # 默认返回openai
    
    def is_provider_available(self, provider):
        """检查指定的AI提供商是否可用"""
        return provider in self.get_available_providers()

# 全局配置实例
app_config = SimpleConfig()
ai_config = SimpleAIConfig()

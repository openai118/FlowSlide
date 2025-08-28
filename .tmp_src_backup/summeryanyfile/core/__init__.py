"""
核心模块 - 包含数据模型、文档处理、LLM管理等核心功能
"""

from .document_processor import DocumentProcessor
from .file_cache_manager import FileCacheManager
from .json_parser import JSONParser
from .llm_manager import LLMManager
from .models import ChunkStrategy, PPTState, SlideInfo

__all__ = [
    "SlideInfo",
    "PPTState",
    "ChunkStrategy",
    "DocumentProcessor",
    "LLMManager",
    "JSONParser",
    "FileCacheManager",
]

"""
配置模块 - 包含设置管理和提示模板
"""

from .prompts import PromptTemplates
from .settings import Settings, load_settings

__all__ = [
    "Settings",
    "load_settings",
    "PromptTemplates",
]

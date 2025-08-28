"""
Base classes for AI providers
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel


class MessageRole(str, Enum):
    """Message roles for AI conversations"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIMessage(BaseModel):
    """AI message model"""

    role: MessageRole
    content: str
    name: Optional[str] = None


class AIResponse(BaseModel):
    """AI response model"""

    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AIProvider(ABC):
    """Abstract base class for AI providers"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = config.get("model", "unknown")

    @abstractmethod
    async def chat_completion(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate chat completion"""
        pass

    @abstractmethod
    async def text_completion(self, prompt: str, **kwargs) -> AIResponse:
        """Generate text completion"""
        pass

    async def stream_chat_completion(
        self, messages: List[AIMessage], **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion (optional)"""
        # Default implementation: return full response at once
        response = await self.chat_completion(messages, **kwargs)
        yield response.content

    async def stream_text_completion(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream text completion (optional)"""
        # Default implementation: return full response at once
        response = await self.text_completion(prompt, **kwargs)
        yield response.content

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "model": self.model,
            "provider": self.__class__.__name__,
            "config": {k: v for k, v in self.config.items() if "key" not in k.lower()},
        }

    def _calculate_usage(self, prompt: str, response: str) -> Dict[str, int]:
        """Calculate token usage (simplified)"""
        # Simplified calculation
        prompt_tokens = len(prompt.split())
        completion_tokens = len(response.split())

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    def _merge_config(self, **kwargs) -> Dict[str, Any]:
        """Merge provider config with request parameters"""
        merged = self.config.copy()
        merged.update(kwargs)
        return merged

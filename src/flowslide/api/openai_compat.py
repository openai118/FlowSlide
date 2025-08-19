"""
OpenAI-compatible API endpoints for FlowSlide.

Provides compatible routes:
- GET /v1/models
- POST /v1/chat/completions
- POST /v1/completions
"""

from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..services.ai_service import AIService
from .models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    Usage,
)

router = APIRouter()

MODELS = [
    {
        "id": "flowslide-v1",
        "object": "model",
        "created": 1642521600,
        "owned_by": "flowslide",
        "permission": [],
        "root": "flowslide-v1",
        "parent": None,
    },
    {
        "id": "flowslide-ppt-generator",
        "object": "model",
        "created": 1642521600,
        "owned_by": "flowslide",
        "permission": [],
        "root": "flowslide-ppt-generator",
        "parent": None,
    },
]

ai_service = AIService()


@router.get("/models")
async def list_models():
    return {"object": "list", "data": MODELS}


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(request: ChatCompletionRequest):
    try:
        last_message = request.messages[-1].content if request.messages else ""

        if getattr(request, "stream", False):

            async def chat_stream() -> AsyncGenerator[bytes, None]:
                if ai_service.is_ppt_request(last_message):
                    content = await ai_service.handle_ppt_chat_request(request)
                else:
                    content = await ai_service.handle_general_chat_request(request)
                chunk = {
                    "id": "chatcmpl-stream",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                }
                yield (f"data: {chunk}\n\n").encode("utf-8")
                yield b"data: [DONE]\n\n"

            return StreamingResponse(chat_stream(), media_type="text/event-stream")

        if ai_service.is_ppt_request(last_message):
            response_content = await ai_service.handle_ppt_chat_request(request)
        else:
            response_content = await ai_service.handle_general_chat_request(request)

        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        completion_tokens = len(response_content.split())
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        choice = ChatCompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=response_content),
            finish_reason="stop",
        )
        return ChatCompletionResponse(model=request.model, choices=[choice], usage=usage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/completions", response_model=CompletionResponse)
async def create_completion(request: CompletionRequest):
    try:
        prompt = request.prompt if isinstance(request.prompt, str) else request.prompt[0]

        if getattr(request, "stream", False):

            async def text_stream() -> AsyncGenerator[bytes, None]:
                if ai_service.is_ppt_request(prompt):
                    content = await ai_service.handle_ppt_completion_request(request)
                else:
                    content = await ai_service.handle_general_completion_request(request)
                chunk = {
                    "id": "cmpl-stream",
                    "object": "text_completion.chunk",
                    "choices": [{"index": 0, "text": content, "finish_reason": None}],
                }
                yield (f"data: {chunk}\n\n").encode("utf-8")
                yield b"data: [DONE]\n\n"

            return StreamingResponse(text_stream(), media_type="text/event-stream")

        if ai_service.is_ppt_request(prompt):
            response_content = await ai_service.handle_ppt_completion_request(request)
        else:
            response_content = await ai_service.handle_general_completion_request(request)

        prompt_tokens = (
            len(prompt.split()) if isinstance(prompt, str) else sum(len(p.split()) for p in prompt)
        )
        completion_tokens = len(response_content.split())
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        choice = CompletionChoice(index=0, text=response_content, finish_reason="stop")
        return CompletionResponse(model=request.model, choices=[choice], usage=usage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

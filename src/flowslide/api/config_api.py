"""
Configuration management API for FlowSlide
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth.middleware import (
    get_current_admin_user,
    get_current_user_optional,
    get_current_user_required,
)
from ..database.models import User
from ..services.config_service import ConfigService, get_config_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]


class DefaultProviderRequest(BaseModel):
    provider: str


# --- Helpers to redact secrets in API responses ---
def _redact_with_schema(values: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of values with password-type fields removed (empty)."""
    redacted = {}
    for k, v in values.items():
        try:
            field = schema.get(k, {})
            if field.get("type") == "password":
                # Do not return actual value
                redacted[k] = ""
            else:
                redacted[k] = v
        except Exception:
            redacted[k] = v
    return redacted


def _heuristic_redact(values: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristically redact secrets (for objects without schema)."""
    sensitive_keywords = ("api_key", "apikey", "token", "secret", "password", "key")
    redacted = {}
    for k, v in values.items():
        if any(kw in k.lower() for kw in sensitive_keywords):
            redacted[k] = ""
        else:
            redacted[k] = v
    return redacted


# Specific routes first (before generic {category} route)
@router.get("/api/config/current-provider")
async def get_current_provider(
    config_service: ConfigService = Depends(get_config_service),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Get current default AI provider (provider config redacted)."""
    try:
        # Get current provider from config service instead of ai_config
        config = config_service.get_config_by_category("ai_providers")
        provider = config.get("default_ai_provider", "openai")
        
        logger.info(f"Current provider from config service: {provider} (type: {type(provider)})")

        # 确保provider不为None或空字符串
        if not provider:
            logger.warning("Provider is None or empty, using default 'openai'")
            provider = "openai"

        # Get provider config - simplified to avoid ai_config issues
        provider_config = {}
        try:
            from ..core.config import ai_config
            if hasattr(ai_config, "get_provider_config"):
                provider_config_raw = ai_config.get_provider_config(provider)
                provider_config = _heuristic_redact(
                    provider_config_raw if isinstance(provider_config_raw, dict) else {}
                )
        except Exception as e:
            logger.warning(f"Could not get provider config: {e}")
            provider_config = {}

        result = {
            "success": True,
            "current_provider": provider,
            "provider_config": provider_config,
        }
        logger.info(f"Returning current provider result: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to get current provider: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get current provider")


@router.post("/api/config/default-provider")
async def set_default_provider(
    request: DefaultProviderRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Set default AI provider"""
    try:
        success = config_service.update_config({"default_ai_provider": request.provider})

        if success:
            # Verify the configuration was applied
            from ..core.config import ai_config

            current_provider = ai_config.default_ai_provider

            return {
                "success": True,
                "message": f"Default provider set to {request.provider}",
                "current_provider": current_provider,
                "config_applied": current_provider == request.provider,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to set default provider")

    except Exception as e:
        logger.error(f"Failed to set default provider: {e}")
        raise HTTPException(status_code=500, detail="Failed to set default provider")


@router.get("/api/config/schema")
async def get_config_schema(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Get configuration schema"""
    try:
        schema = config_service.get_config_schema()
        return {"success": True, "schema": schema}
    except Exception as e:
        logger.error(f"Failed to get configuration schema: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration schema")


@router.post("/api/config/validate")
async def validate_config(
    request: ConfigUpdateRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Validate configuration values"""
    try:
        errors = config_service.validate_config(request.config)
        return {"success": len(errors) == 0, "errors": errors}
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate configuration")


@router.post("/api/config/reset/{category}")
async def reset_config_category(
    category: str,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Reset configuration category to defaults"""
    try:
        success = config_service.reset_to_defaults(category)

        if success:
            return {
                "success": True,
                "message": f"Configuration for {category} reset to defaults",
            }
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to reset configuration for {category}"
            )

    except Exception as e:
        logger.error(f"Failed to reset configuration for category {category}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset configuration for {category}")


@router.post("/api/config/reset")
async def reset_all_config(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Reset all configuration to defaults"""
    try:
        success = config_service.reset_to_defaults()

        if success:
            return {"success": True, "message": "All configuration reset to defaults"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset configuration")

    except Exception as e:
        logger.error(f"Failed to reset configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset configuration")


# Generic routes last
@router.get("/api/config/all")
async def get_all_config(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Get all configuration values (secrets redacted)."""
    try:
        config = config_service.get_all_config()
        schema = config_service.get_config_schema()
        return {"success": True, "config": _redact_with_schema(config, schema)}
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")


@router.get("/api/config/{category}")
async def get_config_by_category(
    category: str,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Get configuration values by category (secrets redacted)."""
    try:
        config = config_service.get_config_by_category(category)
        schema = config_service.get_config_schema()
        # Build a sub-schema for the category
        sub_schema = {k: v for k, v in schema.items() if v.get("category") == category}
        return {
            "success": True,
            "config": _redact_with_schema(config, sub_schema),
            "category": category,
        }
    except Exception as e:
        logger.error(f"Failed to get configuration for category {category}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get configuration for category {category}",
        )


@router.post("/api/config/all")
async def update_all_config(
    request: ConfigUpdateRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Update all configuration values"""
    try:
        # Validate configuration
        errors = config_service.validate_config(request.config)
        if errors:
            return {"success": False, "errors": errors}

        # Update configuration
        success = config_service.update_config(request.config)

        if success:
            return {"success": True, "message": "Configuration updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update configuration")

    except Exception as e:
        logger.error(f"Failed to update configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")


@router.post("/api/config/{category}")
async def update_config_by_category(
    category: str,
    request: ConfigUpdateRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    """Update configuration values for a specific category"""
    try:
        # Validate configuration
        errors = config_service.validate_config(request.config)
        if errors:
            return {"success": False, "errors": errors}

        # Update configuration
        success = config_service.update_config_by_category(category, request.config)

        if success:
            return {
                "success": True,
                "message": f"Configuration for {category} updated successfully",
            }
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to update configuration for {category}"
            )

    except Exception as e:
        logger.error(f"Failed to update configuration for category {category}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update configuration for {category}"
        )

"""Configuration management API for FlowSlide.

Admin-only endpoints to inspect/update application configuration. Secrets
are redacted in responses.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.middleware import get_current_admin_user
from ..database.models import User
from ..services.config_service import ConfigService, get_config_service

logger = logging.getLogger(__name__)
router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]


class DefaultProviderRequest(BaseModel):
    provider: str


def _redact_with_schema(values: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}
    for k, v in (values or {}).items():
        try:
            field = schema.get(k, {})
            if field.get("type") == "password":
                redacted[k] = ""
            else:
                redacted[k] = v
        except Exception:
            redacted[k] = v
    return redacted


def _heuristic_redact(values: Dict[str, Any]) -> Dict[str, Any]:
    sensitive_keywords = ("api_key", "apikey", "token", "secret", "password", "key")
    redacted: Dict[str, Any] = {}
    for k, v in (values or {}).items():
        if any(kw in k.lower() for kw in sensitive_keywords):
            redacted[k] = ""
        else:
            redacted[k] = v
    return redacted


@router.get("/api/config/current-provider")
async def get_current_provider(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        cfg = config_service.get_config_by_category("ai_providers") or {}
        provider = cfg.get("default_ai_provider") or "openai"
        provider_config = {}
        try:
            from ..core.config import ai_config

            if hasattr(ai_config, "get_provider_config"):
                prov_raw = ai_config.get_provider_config(provider)
                if isinstance(prov_raw, dict):
                    provider_config = _heuristic_redact(prov_raw)
        except Exception:
            provider_config = {}

        return {"success": True, "current_provider": provider, "provider_config": provider_config}
    except Exception as e:
        logger.error("Failed to get current provider: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get current provider")


@router.post("/api/config/default-provider")
async def set_default_provider(
    request: DefaultProviderRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        ok = config_service.update_config({"default_ai_provider": request.provider})
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to set default provider")
        try:
            from ..core.config import ai_config

            current_provider = getattr(ai_config, "default_ai_provider", None)
        except Exception:
            current_provider = None
        return {
            "success": True,
            "message": f"Default provider set to {request.provider}",
            "current_provider": current_provider,
            "config_applied": current_provider == request.provider,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to set default provider: %s", e)
        raise HTTPException(status_code=500, detail="Failed to set default provider")


@router.get("/api/config/schema")
async def get_config_schema(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        schema = config_service.get_config_schema()
        return {"success": True, "schema": schema}
    except Exception as e:
        logger.error("Failed to get configuration schema: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get configuration schema")


@router.post("/api/config/validate")
async def validate_config(
    request: ConfigUpdateRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        errors = config_service.validate_config(request.config)
        return {"success": len(errors) == 0, "errors": errors}
    except Exception as e:
        logger.error("Failed to validate configuration: %s", e)
        raise HTTPException(status_code=500, detail="Failed to validate configuration")


@router.post("/api/config/reset/{category}")
async def reset_config_category(
    category: str,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        ok = config_service.reset_to_defaults(category)
        if ok:
            return {"success": True, "message": f"Configuration for {category} reset to defaults"}
        raise HTTPException(status_code=500, detail=f"Failed to reset configuration for {category}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reset configuration for category %s: %s", category, e)
        raise HTTPException(status_code=500, detail=f"Failed to reset configuration for {category}")


@router.post("/api/config/reset")
async def reset_all_config(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        ok = config_service.reset_to_defaults()
        if ok:
            return {"success": True, "message": "All configuration reset to defaults"}
        raise HTTPException(status_code=500, detail="Failed to reset configuration")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reset configuration: %s", e)
        raise HTTPException(status_code=500, detail="Failed to reset configuration")


@router.get("/api/config/all")
async def get_all_config(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        cfg = config_service.get_all_config() or {}
        schema = config_service.get_config_schema() or {}
        return {"success": True, "config": _redact_with_schema(cfg, schema)}
    except Exception as e:
        logger.error("Failed to get configuration: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get configuration")


@router.get("/api/config/{category}")
async def get_config_by_category(
    category: str,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        cfg = config_service.get_config_by_category(category) or {}
        schema = config_service.get_config_schema() or {}
        sub_schema = {k: v for k, v in schema.items() if v.get("category") == category}
        return {
            "success": True,
            "config": _redact_with_schema(cfg, sub_schema),
            "category": category,
        }
    except Exception as e:
        logger.error("Failed to get configuration for category %s: %s", category, e)
        detail_msg = f"Failed to get configuration for category {category}"
    raise HTTPException(status_code=500, detail=detail_msg)


@router.post("/api/config/all")
async def update_all_config(
    request: ConfigUpdateRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        errors = config_service.validate_config(request.config)
        if errors:
            return {"success": False, "errors": errors}
        ok = config_service.update_config(request.config)
        if ok:
            return {"success": True, "message": "Configuration updated successfully"}
        raise HTTPException(status_code=500, detail="Failed to update configuration")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update configuration: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update configuration")


@router.post("/api/config/{category}")
async def update_config_by_category(
    category: str,
    request: ConfigUpdateRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        errors = config_service.validate_config(request.config)
        if errors:
            return {"success": False, "errors": errors}
        ok = config_service.update_config_by_category(category, request.config)
        if ok:
            return {
                "success": True,
                "message": f"Configuration for {category} updated successfully",
            }
        detail_msg = f"Failed to update configuration for {category}"
        raise HTTPException(status_code=500, detail=detail_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update configuration for category %s: %s", category, e)
        detail_msg = f"Failed to update configuration for {category}"
        raise HTTPException(status_code=500, detail=detail_msg)

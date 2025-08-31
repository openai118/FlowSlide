"""Configuration management API for FlowSlide.

Admin-only endpoints to inspect/update application configuration. Secrets
are redacted in responses.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
import re
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
                # If a password/secret exists, return a masked placeholder so the UI
                # can detect that a secret is present without exposing it.
                if v:
                    redacted[k] = "••••••••"
                else:
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


# Mask placeholder used in UI for secrets
MASKED_PLACEHOLDER = "••••••••"


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
        # Admin-only endpoint: return raw configuration values (admins need full access)
        cfg = config_service.get_all_config() or {}
        schema = config_service.get_config_schema() or {}
        # Return raw config for admins, masked for others
        if getattr(user, "is_admin", False):
            return {"success": True, "config": cfg}
        else:
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
        # Admin-only: return raw config values for the requested category
        cfg = config_service.get_config_by_category(category) or {}
        schema = config_service.get_config_schema() or {}
        if getattr(user, "is_admin", False):
            return {"success": True, "config": cfg, "category": category}
        else:
            return {"success": True, "config": _redact_with_schema(cfg, schema), "category": category}
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
        # Remove masked placeholders for password fields to avoid overwriting secrets
        schema = config_service.get_config_schema() or {}
        cleaned = {}
        for k, v in (request.config or {}).items():
            # If schema marks this as a password and the value equals the masked placeholder,
            # skip it (treat as no-change)
            if k in schema and schema[k].get("type") == "password" and v == MASKED_PLACEHOLDER:
                continue
            cleaned[k] = v

        errors = config_service.validate_config(cleaned)
        if errors:
            return {"success": False, "errors": errors}
        ok = config_service.update_config(cleaned)
        if ok:
            return {"success": True, "message": "Configuration updated successfully"}
        raise HTTPException(status_code=500, detail="Failed to update configuration")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update configuration: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update configuration")


@router.post("/api/config/category/{category}")
async def update_config_by_category(
    category: str,
    request: ConfigUpdateRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_admin_user),
):
    try:
        # Filter incoming payload to keys that belong to this category per schema
        schema = config_service.get_config_schema() or {}
        filtered = {k: v for k, v in (request.config or {}).items() if k in schema and schema[k].get("category") == category}

        # Remove masked placeholders for password fields
        filtered = {k: v for k, v in filtered.items() if not (schema.get(k, {}).get("type") == "password" and v == MASKED_PLACEHOLDER)}

        # Validate only the filtered keys to avoid unknown-key errors for unrelated inputs
        errors = config_service.validate_config(filtered)
        if errors:
            return {"success": False, "errors": errors}

        ok = config_service.update_config_by_category(category, filtered)
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



@router.post("/api/config/parse-and-apply")
async def parse_and_apply_config(request: ConfigUpdateRequest, config_service: ConfigService = Depends(get_config_service), user: User = Depends(get_current_admin_user)):
    """Parse bulk text containing KEY=VALUE lines (or semicolon separated) and apply to configuration."""
    try:
        raw = request.config.get('raw', '') if isinstance(request.config, dict) else ''
        if not raw:
            raise HTTPException(status_code=400, detail="Missing raw configuration text under 'raw' key")

        # 简单解析：按行或分号拆分，忽略注释
        kv = {}
        parts = [p.strip() for p in re.split(r"[\r\n;]+", raw) if p.strip()]
        for part in parts:
            if part.startswith('#'):
                continue
            if '=' not in part:
                continue
            k, v = part.split('=', 1)
            kv[k.strip()] = v.strip()

        if not kv:
            return {"success": False, "message": "No key=value pairs found"}

        # Map common env var names to internal config keys (lowercase)
        normalized = {k.lower(): v for k, v in kv.items()}

        # Validate R2 completeness: require all four before marking configured
        r2_keys = ['r2_access_key_id', 'r2_secret_access_key', 'r2_endpoint', 'r2_bucket_name']
        has_all_r2 = all(normalized.get(k) for k in r2_keys)

        # Prepare update dict: map to config schema keys where applicable
        update_payload = {}
        # direct mappings
        direct_map = {
            'r2_access_key_id': 'r2_access_key_id',
            'r2_secret_access_key': 'r2_secret_access_key',
            'r2_endpoint': 'r2_endpoint',
            'r2_bucket_name': 'r2_bucket_name',
            'storage_bucket': 'storage_bucket',
            'storage_provider': 'storage_provider',
            'database_url': 'database_url',
            'api_url': 'api_url',
            'api_anon_key': 'api_anon_key',
            'api_service_key': 'api_service_key'
        }

        for k, v in normalized.items():
            if k in direct_map:
                update_payload[direct_map[k]] = v

        # If R2 not complete, clear R2 fields to avoid partial detection
        if not has_all_r2:
            for rk in r2_keys:
                update_payload.pop(rk, None)

        # Filter update_payload to known schema keys to avoid unknown-key errors (e.g., accidental 'raw')
        schema_keys = set(config_service.get_config_schema().keys() or [])
        filtered_payload = {k: v for k, v in update_payload.items() if k in schema_keys}

        # Apply to config store
        errors = config_service.validate_config(filtered_payload)
        if errors:
            return {"success": False, "errors": errors}

        ok = config_service.update_config(filtered_payload)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to update configuration")

        return {"success": True, "applied": list(filtered_payload.keys()), "r2_configured": has_all_r2}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("parse_and_apply_config error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to parse and apply configuration")

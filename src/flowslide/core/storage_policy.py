"""Deterministic storage selection; connectivity must never select an identity store."""

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional
from urllib.parse import urlsplit

DEPLOYMENT_MODES = frozenset({"local_only", "local_external", "local_r2", "local_external_r2"})
EXTERNAL_MODES = frozenset({"local_external", "local_external_r2"})
R2_MODES = frozenset({"local_r2", "local_external_r2"})


@dataclass(frozen=True)
class StoragePolicy:
    mode: str
    external_url: str = field(default="", repr=False)

    @property
    def uses_external(self) -> bool:
        return self.mode in EXTERNAL_MODES

    @property
    def uses_r2(self) -> bool:
        return self.mode in R2_MODES

    @property
    def authentication_source(self) -> str:
        return "external" if self.uses_external else "local"


def configured_storage_policy(
    environ: Optional[Mapping[str, str]] = None,
) -> StoragePolicy:
    """Resolve pinned mode first, then legacy DATABASE_MODE, then configured services.

    Health probes are deliberately excluded: a PostgreSQL outage must not expose
    a different SQLite administrator account or change a user's password store.
    """
    env = os.environ if environ is None else environ
    external_url = (env.get("EXTERNAL_DATABASE_URL") or env.get("DATABASE_URL") or "").strip()
    if external_url.startswith("postgres://"):
        external_url = "postgresql://" + external_url[len("postgres://") :]
    elif external_url.startswith("postgres+"):
        external_url = "postgresql+" + external_url[len("postgres+") :]
    scheme = urlsplit(external_url).scheme.lower().split("+", 1)[0]
    has_external = scheme in {"postgres", "postgresql", "mysql"}
    has_r2 = all(
        env.get(key)
        for key in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET_NAME")
    )
    pinned = (
        (env.get("DEPLOYMENT_PINNED_MODE") or env.get("FORCE_DEPLOYMENT_MODE") or "")
        .strip()
        .lower()
    )
    if pinned:
        if pinned not in DEPLOYMENT_MODES:
            raise ValueError("DEPLOYMENT_PINNED_MODE 不是有效的部署模式")
        mode = pinned
    else:
        legacy = (env.get("DATABASE_MODE") or "").strip().lower()
        if legacy not in {"", "local", "external", "hybrid"}:
            raise ValueError("DATABASE_MODE 必须是 local、external 或 hybrid")
        use_external = legacy in {"external", "hybrid"} or (not legacy and has_external)
        if use_external:
            mode = "local_external_r2" if has_r2 else "local_external"
        else:
            mode = "local_r2" if has_r2 else "local_only"
    if mode in EXTERNAL_MODES and not has_external:
        raise ValueError("外部数据库模式必须配置有效的 PostgreSQL/MySQL DATABASE_URL")
    return StoragePolicy(mode=mode, external_url=external_url if has_external else "")

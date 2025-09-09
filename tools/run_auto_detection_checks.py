import asyncio
import os
import sys
import types

# Ensure repo src is on sys.path so package imports work when running this script
from pathlib import Path
repo_root = Path(__file__).resolve().parents[1]
src_path = str(repo_root / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)


def _patch_async_engine_failure(module):
    def fake_create_async_engine_safe(url, echo=False, connect_args=None):
        class FakeConn:
            async def __aenter__(self):
                raise Exception("simulated asyncpg failure")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeEngine:
            def connect(self):
                return FakeConn()

            async def dispose(self):
                return None

        return FakeEngine()

    module.create_async_engine_safe = fake_create_async_engine_safe


def _install_fake_psycopg2():
    fake_psycopg2 = types.SimpleNamespace()

    def fake_connect(url, connect_timeout=5):
        class Conn:
            def cursor(self):
                class Cur:
                    def execute(self, q):
                        pass

                    def fetchone(self):
                        return (1,)

                    def close(self):
                        pass

                return Cur()

            def close(self):
                pass

        return Conn()

    fake_psycopg2.connect = fake_connect
    sys.modules["psycopg2"] = fake_psycopg2


async def run_check(disable_sync_fallback=False):
    # Import inside function to avoid side-effects at module import time
    from flowslide.core import auto_detection_service as ads_mod
    from flowslide.core.auto_detection_service import AutoDetectionService

    # Ensure detection will try external DB
    os.environ["EXTERNAL_DATABASE_URL"] = os.getenv("EXTERNAL_DATABASE_URL", "postgresql://user:pass@host:5432/db")
    os.environ["LOCAL_DATABASE_URL"] = os.getenv("LOCAL_DATABASE_URL", "sqlite:///./data/flowslide.db")
    if disable_sync_fallback:
        os.environ["DISABLE_SYNC_DB_FALLBACK"] = "1"
    else:
        os.environ.pop("DISABLE_SYNC_DB_FALLBACK", None)

    # Patch async engine to fail
    _patch_async_engine_failure(ads_mod)

    if not disable_sync_fallback:
        _install_fake_psycopg2()
    else:
        if "psycopg2" in sys.modules:
            del sys.modules["psycopg2"]

    svc = AutoDetectionService()
    res = await svc.check_external_database()
    return res


def main():
    print("Running auto-detection async-fail -> sync-fallback check (enabled)")
    r = asyncio.run(run_check(disable_sync_fallback=False))
    print(vars(r))

    print("\nRunning auto-detection with sync fallback disabled")
    r2 = asyncio.run(run_check(disable_sync_fallback=True))
    print(vars(r2))


if __name__ == "__main__":
    main()

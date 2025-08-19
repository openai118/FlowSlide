#!/usr/bin/env python3
"""
FlowSlide Application Runner

This script starts the FlowSlide FastAPI application with proper configuration.
"""

import uvicorn
import sys
import os
import asyncio
from dotenv import load_dotenv

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Load environment variables with error handling
try:
    load_dotenv()
except PermissionError as e:
    print(f"Warning: Could not load .env file due to permission error: {e}")
    print("Continuing with system environment variables...")
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")
    print("Continuing with system environment variables...")

def main():
    """Main entry point for running the application"""

    # Workaround for Windows asyncio subprocess (Playwright/Chromium) issues
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            print("✅ Windows event loop set to Proactor (supports subprocess)")
        except Exception as e:
            print(f"⚠️ Failed to set Windows ProactorEventLoopPolicy: {e}")

    # Get configuration from environment variables with defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() in ("true", "1", "yes", "on")
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    # Configuration
    config = {
        "app": "flowslide.main:app",
        "host": host,
        "port": port,
        "reload": reload,
        "log_level": log_level,
        "access_log": True,
    }

    print("🚀 Starting FlowSlide Server...")
    print(f"🏷️ Host: {config['host']}")
    print(f"🔌 Port: {config['port']}")
    print(f"🔄 Reload: {config['reload']}")
    print(f"📊 Log Level: {config['log_level']}")
    print(f"🔗 Server: http://localhost:{config['port']}")
    print(f"🏠 Home (public): http://localhost:{config['port']}/home")
    print(f"📚 API Docs: http://localhost:{config['port']}/docs")
    print("=" * 60)

    try:
        uvicorn.run(**config)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

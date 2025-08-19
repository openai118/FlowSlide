#!/usr/bin/env python3
"""
Quick Database Check Script for FlowSlide
Performs basic database connectivity and health checks
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def check_database():
    """Check database connectivity and basic health"""
    try:
        from flowslide.database.database import init_db, get_database
        
        print("🔍 Checking database connectivity...")
        
        # Initialize database
        await init_db()
        print("✅ Database initialization successful")
        
        # Get database instance
        db = get_database()
        if db:
            print("✅ Database connection established")
            
            # Try a simple query
            try:
                # This will work with both SQLite and PostgreSQL
                result = await db.fetch_all("SELECT 1 as test")
                if result:
                    print("✅ Database query test successful")
                else:
                    print("⚠️ Database query returned no results")
            except Exception as e:
                print(f"⚠️ Database query test failed: {e}")
                
        else:
            print("❌ Failed to get database connection")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import database modules: {e}")
        return False
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

async def main():
    """Main function"""
    print("🚀 FlowSlide Quick Database Check")
    print("=" * 40)
    
    try:
        success = await check_database()
        
        if success:
            print("=" * 40)
            print("✅ Database check completed successfully")
            sys.exit(0)
        else:
            print("=" * 40)
            print("❌ Database check failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Set up basic logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run the check
    asyncio.run(main())

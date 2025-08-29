#!/usr/bin/env python3
"""
手动触发同步
"""

import asyncio
import sys
sys.path.append('src')

async def manual_sync():
    try:
        from flowslide.services.data_sync_service import trigger_manual_sync

        print('🔄 正在手动触发同步...')
        result = await trigger_manual_sync()

        print(f'同步结果: {result["status"]}')
        if 'message' in result:
            print(f'消息: {result["message"]}')

    except Exception as e:
        print(f'同步失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(manual_sync())

import os
from src.flowslide.core.simple_config import DATABASE_MODE
print('DATABASE_MODE=', DATABASE_MODE)
print('INIT_ADMIN_STRATEGY=', os.getenv('INIT_ADMIN_STRATEGY','external-first'))
print('INIT_ADMIN_FALLBACK=', os.getenv('INIT_ADMIN_FALLBACK','true'))

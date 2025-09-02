import os
from src.flowslide.core.simple_config import DATABASE_MODE
from src.flowslide.database import database as dbmod
print('DATABASE_MODE=', DATABASE_MODE)
print('ACTIVE_DEPLOYMENT_MODE=', os.getenv('ACTIVE_DEPLOYMENT_MODE'))
print('external_engine configured=', hasattr(dbmod.db_manager, 'external_engine') and dbmod.db_manager.external_engine is not None)
print('R2 configured (access key present)=', bool(os.getenv('R2_ACCESS_KEY_ID')))

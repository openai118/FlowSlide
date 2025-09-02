import os
from src.flowslide.core.simple_config import DATABASE_MODE
from src.flowslide.database import database as dbmod
print('DATABASE_MODE=', DATABASE_MODE)
print('external_engine present=', hasattr(dbmod.db_manager, 'external_engine') and dbmod.db_manager.external_engine is not None)
print('external_url=', getattr(dbmod.db_manager, 'external_url', None))

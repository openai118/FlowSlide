import os
from src.flowslide.core.deployment_mode_manager import mode_manager
print('ACTIVE_DEPLOYMENT_MODE=', os.getenv('ACTIVE_DEPLOYMENT_MODE'))
print('mode_manager.current_mode=', mode_manager.current_mode)
print('detected_mode=', mode_manager.detect_current_mode().value)

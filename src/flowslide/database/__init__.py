"""Lazy public exports; importing a model must not initialize the application."""

from importlib import import_module

_EXPORTS = {'SessionLocal': ('.database', 'SessionLocal'), 'engine': ('.database', 'engine'), 'get_async_db': ('.database', 'get_async_db'), 'get_db': ('.database', 'get_db'), 'init_db': ('.database', 'init_db'), 'db_manager': ('.database', 'db_manager'), 'health_checker': ('.health_check', 'health_checker'), 'migration_manager': ('.migrations', 'migration_manager'), 'PPTTemplate': ('.models', 'PPTTemplate'), 'Project': ('.models', 'Project'), 'ProjectVersion': ('.models', 'ProjectVersion'), 'SlideData': ('.models', 'SlideData'), 'TodoBoard': ('.models', 'TodoBoard'), 'TodoStage': ('.models', 'TodoStage'), 'PPTTemplateRepository': ('.repositories', 'PPTTemplateRepository'), 'ProjectRepository': ('.repositories', 'ProjectRepository'), 'ProjectVersionRepository': ('.repositories', 'ProjectVersionRepository'), 'SlideDataRepository': ('.repositories', 'SlideDataRepository'), 'TodoBoardRepository': ('.repositories', 'TodoBoardRepository'), 'TodoStageRepository': ('.repositories', 'TodoStageRepository'), 'DatabaseService': ('.service', 'DatabaseService')}

__all__ = ['engine', 'SessionLocal', 'get_db', 'get_async_db', 'init_db', 'db_manager', 'Project', 'TodoBoard', 'TodoStage', 'ProjectVersion', 'SlideData', 'PPTTemplate', 'migration_manager', 'health_checker', 'DatabaseService', 'ProjectRepository', 'TodoBoardRepository', 'TodoStageRepository', 'ProjectVersionRepository', 'SlideDataRepository', 'PPTTemplateRepository']

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    return getattr(import_module(module_name, __name__), attribute)

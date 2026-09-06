"""Lazy public exports; importing a model must not initialize the application."""

from importlib import import_module

_EXPORTS = {'AuthService': ('.auth_service', 'AuthService'), 'get_auth_service': ('.auth_service', 'get_auth_service'), 'init_default_admin': ('.auth_service', 'init_default_admin'), 'AuthMiddleware': ('.middleware', 'AuthMiddleware'), 'create_auth_middleware': ('.middleware', 'create_auth_middleware'), 'get_current_admin_user': ('.middleware', 'get_current_admin_user'), 'get_current_user': ('.middleware', 'get_current_user'), 'get_current_user_optional': ('.middleware', 'get_current_user_optional'), 'get_current_user_required': ('.middleware', 'get_current_user_required'), 'get_user_info': ('.middleware', 'get_user_info'), 'is_admin': ('.middleware', 'is_admin'), 'is_authenticated': ('.middleware', 'is_authenticated'), 'require_admin': ('.middleware', 'require_admin'), 'require_auth': ('.middleware', 'require_auth'), 'auth_router': ('.routes', 'router')}

__all__ = ['AuthService', 'get_auth_service', 'init_default_admin', 'AuthMiddleware', 'create_auth_middleware', 'get_current_user', 'require_auth', 'require_admin', 'get_current_user_optional', 'get_current_user_required', 'get_current_admin_user', 'is_authenticated', 'is_admin', 'get_user_info', 'auth_router']

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    return getattr(import_module(module_name, __name__), attribute)

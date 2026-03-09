import sys
from module.config import cfg
from module.logger import log


class _LazyAutomation:
    def __init__(self):
        self._instance = None
        self._import_error = None

    def _get_instance(self):
        if self._instance is None and self._import_error is None:
            try:
                # Clear any partially initialized modules to avoid circular import issues
                modules_to_clear = [
                    'module.automation.automation',
                    'module.automation.screenshot',
                    'module.automation.input_handlers.input',
                ]
                for mod in modules_to_clear:
                    if mod in sys.modules and sys.modules[mod] is None:
                        del sys.modules[mod]
                
                from module.automation.automation import Automation
                self._instance = Automation(cfg.get_value("game_title_name"))
            except Exception as e:
                self._import_error = e
                log.error(f"Failed to initialize Automation: {e}")
                raise
        if self._import_error:
            raise self._import_error
        return self._instance

    def __getattr__(self, item):
        return getattr(self._get_instance(), item)


auto = _LazyAutomation()

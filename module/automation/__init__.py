from module.config import cfg


class _LazyAutomation:
    def __init__(self):
        self._instance = None

    def _get_instance(self):
        if self._instance is None:
            from module.automation.automation import Automation

            self._instance = Automation(cfg.get_value("game_title_name"))
        return self._instance

    def __getattr__(self, item):
        return getattr(self._get_instance(), item)


auto = _LazyAutomation()

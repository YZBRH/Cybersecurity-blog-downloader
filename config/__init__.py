from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._config import Config

config_instance: "Config | None" = None

def get_config():
    global config_instance
    if config_instance is None:
        from ._config import Config
        config_instance = Config()
    return config_instance

class ConfigProxy:
    def __getattr__(self, name):
        return getattr(get_config(), name)

    def __setattr__(self):
        raise AttributeError("Cannot set attributes directly on config proxy")

    def __getitem__(self, key):
        return get_config()[key]

    def __setitem__(self, key, value):
        get_config()[key] = value

    def update(self, new_dict: dict):
        get_config().update(new_dict)
    
    @property
    def data(self) -> dict:
        return get_config().data


CONFIG = ConfigProxy()

if TYPE_CHECKING:
    CONFIG: Config
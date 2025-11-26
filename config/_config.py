from pathlib import Path
from typing import Any, Optional, Dict
import platform
import copy
import tomlkit


def deep_update_in_toml(target, update):
    """
    递归地将 update 字典深度合并到 target (tomlkit TOMLDocument 或 Table)
    """
    for key, value in update.items():
        if key in target and isinstance(target[key], (tomlkit.items.Table, dict)) and isinstance(value, dict):
            deep_update_in_toml(target[key], value)
        else:
            target[key] = value

class Config:
    def __init__(self, config_file=None):
        if config_file is None:
            if Path("config.toml").exists() and Path("config.toml").is_file():
                config_file = Path("config.toml")
            else:
                raise Exception("尚未配置 config.toml 文件")
        self.config_file = config_file

        self._doc = self.read_from_file()
        self._data = self._doc.unwrap()

        if "global" not in self._doc:
            self._doc["global"] = tomlkit.table()

        self._doc["global"]["platform"] = platform.system()

    def read_from_file(self, filepath: Optional[Path] = None) -> tomlkit.TOMLDocument:
        if filepath is None:
            filepath = self.config_file

        if not filepath.exists():
            doc = tomlkit.document()
            doc.add(tomlkit.comment("Auto-generated config file"))
            return doc

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return tomlkit.parse(content)

    def save_to_file(self, filepath: Optional[Path] = None) -> None:
        if filepath is None:
            filepath = self.config_file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(self._doc))

    def __getitem__(self, key: str) -> Any:
        return self._doc[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._doc[key] = value
        self.save_to_file()

    def __delitem__(self, key: str) -> None:
        del self._doc[key]

    def update(self, new_dict: Dict) -> None:
        """
        深度合并 new_dict 到当前配置，并保存
        """
        deep_update_in_toml(self._doc, new_dict)
        self.save_to_file()

    def get(self, key: str, default=None):
        return self._doc.get(key, default)

    @property
    def data(self) -> Dict:
        # 返回深拷贝的纯 dict（不含 tomlkit 对象）
        return copy.deepcopy(self._doc.unwrap())



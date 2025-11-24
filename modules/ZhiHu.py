if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tools import kill_element_by_css_selector
from modules import BaseModule

class ZhiHu(BaseModule):
    def __init__(self, logs: list|None):
        super().__init__(logs)
        self.base_url = ""
        self.TAG = "知乎"
        self.keyword = {
            "keyword": "",  # 搜索关键词(必选)
        }

    def kill_elements(self, driver):
        super().kill_elements(driver)
        selectors = [
        ]
        kill_element_by_css_selector(driver, selectors)


    def wait_to_load(self, driver) -> bool:
        if not super().wait_to_load(driver):
            return False

        return True

    def search(self, search_dict: dict) -> dict:
        if search_dict.get("keyword", None) is None:
            raise ValueError(f"{self.TAG} 未获取到输入关键词")
        
        self.keyword = search_dict
        
        download_event_list = []
        
        params = {
            "keywords": search_dict["keyword"],
        }


        


if __name__ == "__main__":
    zhihu = ZhiHu()
    zhihu.search({"keyword": "CVE"})
    zhihu.download()
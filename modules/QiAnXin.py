import requests
from bs4 import BeautifulSoup

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tools import kill_element_by_css_selector
from modules import BaseModule

class QiAnXin(BaseModule):
    def __init__(self, logs: list|None = None):
        super().__init__(logs)
        self.base_url = "https://forum.butian.net"
        self.TAG = "奇安信攻防社区"
        self.keyword = {
            "keyword": "",  # 搜索关键词(必选)
        }

    def kill_elements(self, driver):
        super().kill_elements(driver)
        selectors = [
            ".navbar.navbar-inverse.navbar-fixed-top",  # 顶部导航栏
            ".col-xs-12.col-md-3.side",  # 页面底栏
            "#footer",  # 底栏
            "#cnzz_stat_icon_1279782571",  # 左下角统计
            ".answer_login_tips.mb-20"  # 登录提示
        ]
        kill_element_by_css_selector(driver, selectors)

    def search(self, search_dict: dict) -> dict:
        if search_dict.get("keyword", None) is None:
            raise ValueError(f"未获取到输入关键词")
        
        self.keyword.update(search_dict)
        
        download_event_list = []
        
        for page in range(1, self.MAX_PAGE):
            self.info(f"开始搜索第{page}页")
            params = {
                "word": search_dict["keyword"],
                "page": str(page),
            }
            res = requests.get(self.base_url + "/search", params=params, headers=self.headers)

            soup = BeautifulSoup(res.text, "html.parser")

            num = int(soup.find("h3", class_="h5 mt0").find("strong").text)
            if num == 0:
                break

            as_ = soup.find_all("a", rel="noopenner noreferrer")
            for a in as_:
                new_download_event = {
                    "url": a.get("href"),
                    "title": a.text.replace("<em>","").replace("</em>","").strip()
                }
                download_event_list.append(new_download_event)
        self.info(f"关键词 {search_dict['keyword']} 共检索到{len(download_event_list)}条下载数据")
        
        self.download_data = {
            "total": len(download_event_list),
            "completed": 0,
            "data": download_event_list
        }
        return self.download_data

if __name__ == "__main__":
    qianxin = QiAnXin()
    qianxin.search({"keyword": "CVE"})
    qianxin.download()
import tls_client

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tools import kill_element_by_css_selector
from modules import BaseModule


class FreeBuf(BaseModule):
    articleType_list = ["资讯", "活动", "技术", "工具", "漏洞", "攻防演练", "AI安全",
                        "开发安全", "web安全", "终端安全", "系统安全", "数据安全", "基础安全",
                        "企业安全", "关基安全", "政策法规", "云安全", "移动安全", "安全招聘",
                        "人物志", "其他"]
    stype_dict = {
        "不限制":"",
        "标题搜索":"title",
        "概要搜索": "description",
        "全文搜索": "context"
    }

    def __init__(self, logs: list|None = None):
        super().__init__(logs)
        self.base_url = "https://www.freebuf.com"
        self.TAG = "FreeBuf"

        self.keyword = {
            "keyword": "",  # 搜索关键词(str)
            "articleType": "",  # 文章类型，可多选，逗号分隔
            "year": "",  # 年份 2018-2025
            "stype": ""  # 关键词匹配范围， 1.标题搜索(title)  2.概要搜索(description)  3.全文搜索(context)
        }
        

    def download_from_url(self, driver, url, save_path) -> None:
        status = super().download_from_url(driver, url, save_path)
        # 清掉cookie以防止下一次访问触发验证码页面
        driver.delete_all_cookies()
        return status

    def kill_elements(self, driver) -> None:
        super().kill_elements(driver)
        remove_elements = [
            "#WAF_NC_WRAPPER",  # 访问验证
            ".waf-nc-mask",  # 访问验证的暗色滤镜
            ".articles-layout-header.ant-layout-header",  # 顶部导航栏
            ".page-header",  # 文章顶部栏
            ".floating-view",  # 右侧悬浮栏
            ".aside-left",  # 左侧栏
            ".aside-right",  # 右侧栏
            ".remix-module",  # 收录栏
            ".introduce",  # 推荐栏
            ".ant-layout-footer"  # 底部栏
            ]
        kill_element_by_css_selector(driver, remove_elements)

    def search(self, search_dict: dict) -> dict:
        if search_dict.get("keyword", None) is None:
            raise ValueError(f"未获取到输入关键词")
        
        self.keyword.update(search_dict)

        download_event_list = []

        params = {
            "content": search_dict["keyword"],
            "articleType": ",".join(search_dict.get("articleType", [])),
            "year": "" if search_dict.get("year", "不限制") == "不限制" else search_dict.get("year", ""),
            "type": self.stype_dict[search_dict.get("stype", "不限制")],
            "time": "0",
            "page": "1",
            "limit": self.MAX_PAGE
        }
        self.info(f"开始搜索关键词[{params['content']}]相关帖子，"
                 f"限制文章类型: {params['articleType']} ，限制年份: {params['year']} ，限制关键词匹配范围: {params['type']}")
        search_url = self.base_url + "/fapi/frontend/search/article"

        session = tls_client.Session(client_identifier="chrome_130")
        res = session.get(search_url, params=params, headers=self.headers)

        if res.status_code != 200:
            self.error(f"检索失败，返回信息：{res}")
            return {}

        if "请进行验证" in res.text:
            self.error("触发人机验证，查询中止")
            return {}
        
        res = res.json()

        search_data_list = res["data"].get("data_list", [])
        for search_data in search_data_list:
            new_download_event = {
                "url": self.base_url + search_data["url"],
                "title": search_data["post_title"].replace("<em>", "").replace("</em>", "")
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
    freebuf = FreeBuf()
    freebuf.search({"keyword": "CVE"})
    
    # freebuf.download()
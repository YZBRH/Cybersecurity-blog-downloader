import requests
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tools import kill_element_by_css_selector
from modules import BaseModule


class CSDN(BaseModule):
    def __init__(self, logs: list|None = None):
        super().__init__(logs)
        self.base_url = "https://www.csdn.net"
        self.TAG = "CSDN"
        self.keyword = {
            "keyword": "",  # 搜索关键词(必选)
        }

    def pretreatment(self, driver) -> bool:
        """
        针对CSDN不同文章类型进行预处理
        :param driver: 浏览器驱动
        :return: 是否继续爬取
        """
        try:
            driver.find_element(By.CSS_SELECTOR, ".vip-mask")
            self.warn("VIP文章，跳过")
            return False
        except NoSuchElementException:
            pass
        
        try:
            driver.find_element(By.CSS_SELECTOR, ".column-mask")
            self.warn("付费文章，跳过")
            return False
        except NoSuchElementException:
            pass

        return True

    def kill_elements(self, driver):
        super().kill_elements(driver)
        selectors = [
            "#toolbarBox",  # 顶部导航栏
            ".csdn-side-toolbar",  # 右侧悬浮栏
            ".passport-login-tip-container.false",  # 登录提示
            ".passport-container.passport-container-mini",  # 登录提示2
            ".blog_container_aside",  # 左侧栏
            ".passport-login-container",  # 登录框
            ".passport-login-tip-container.dark",  # 登录框2
            ".more-toolbox-new.more-toolbar",  # 页面底栏
            "#dmp_ad_58",  # 页面底部广告
            ".recommend-box.insert-baidu-box.recommend-box-style",  # 推荐栏
            ".second-recommend-box.recommend-box",
            ".blog-footer-bottom",  # 底部栏
            "#blogColumnPayAdvert",  # 专栏
            ".hljs-button.signin.active",  # 登录复制按钮
            ".btn-code-notes.mdeditor",  # AI按钮

        ]
        kill_element_by_css_selector(driver, selectors)

    def wait_to_load(self, driver) -> bool:
        if not super().wait_to_load(driver):
            return False
        
        if not self.pretreatment(driver):
            return False
        
        # 绕过“关注博主即可阅读全文”
        jscode = """
            var article_content=document.getElementById("article_content");
            article_content.removeAttribute("style");

            var follow_text=document.getElementsByClassName('follow-text')[0];
            follow_text.parentElement.parentElement.removeChild(follow_text.parentElement);

            var hide_article_box=document.getElementsByClassName(' hide-article-box')[0];
            hide_article_box.parentElement.removeChild(hide_article_box);
        """
        try:
            driver.execute_script(jscode)
        except:
            pass

        # 绕过代码复制限制
        driver.execute_script("document.body.contentEditable='true'")

        return True

    def search(self, search_dict: dict) -> dict:
        if search_dict.get("keyword", None) is None:
            raise ValueError(f"未获取到输入关键词")
        
        self.keyword.update(search_dict)
        
        download_event_list = []

        for page in range(1, self.MAX_PAGE):
            self.info(f"开始搜索第{page}页")
            params = {
                "q": search_dict["keyword"],  # 关键词
                "t": "blog",  # 类型
                "p": str(page),  # 页码
                "s": "0",
                "tm": "0",
                "lv": "-1",
                "ft": "0",
                "l": "",
                "u": "",
                "ct": "-1",
                "pnt": "-1",
                "ry": "-1",
                "ss": "-1",
                "dct": "-1",
                "vco": "-1",
                "cc": "-1",
                "sc": "-1",
                "akt": "-1",
                "art": "-1",
                "ca": "-1",
                "prs": "",
                "pre": "",
                "ecc": "-1",
                "ebc": "-1",
                "urw": "",
                "ia": "1",
                "dId": "",
                "cl": "-1",
                "scl": "-1",
                "tcl": "-1",
                "platform": "pc",
                "ab_test_code_overlap": "",
                "ab_test_random_code": "",
                "trace_id": ""
            }
            res = requests.get("https://so.csdn.net/api/v3/search", headers=self.headers, params=params).json()
            
            datas = res.get("result_vos", [])
            if datas is None or len(datas) == 0:
                break
            for data in datas:
                new_download_event = {
                    "url": data["url"].split("?")[0],
                    "title": data["title"].strip("<em>").strip("</em>")
                }
                download_event_list.append(new_download_event)
        self.info(f"关键词 {search_dict['keyword']} 共检索到{len(download_event_list)}条下载数据")

        self.download_data = {
            "total": len(download_event_list),
            "completed": 0,
            "data": download_event_list
        }
        return self.download_data

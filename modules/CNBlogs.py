import requests
from bs4 import BeautifulSoup
import base64
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tools import kill_element_by_css_selector, get_web_driver
from modules import BaseModule

class CNBlogs(BaseModule):
    time_dict = {
        "不限制": "",
        "一周内": "1",
        "一月内": "2",
        "三月内": "3",
        "一年内": "4"
    }

    def __init__(self, logs: list | None):
        super().__init__(logs)
        self.base_url = "https://zzk.cnblogs.com"
        self.TAG = "博客园"
        self.cookies = {
            "zzk-captcha": "CfDJ8CE1tT_puDpHgc1zrpsLVP9LTMFy6VjVB1B2AUlsJCs7Hoii11y3K2UczsyAtq6f1DZGtovKvqyWMB4U_cEqdZqiJ59-7hUdhosRLiGOMEofkcL_5FtrxHG7_21TVt6L8Q"
        }

        self.keyword = {
            "keyword": "",  # 搜索关键词(必选)
            "ViewCount": "",  # 浏览量下限
            "DiggCount": "",  # 推荐数下限
            "DateTimeRange": ""  # 时间范围 1.一周内  2.一月内  3.三月内  4.一年内
        }
        self.try_limit = 10  # 验证码绕过尝试次数上限

    def kill_elements(self, driver):
        super().kill_elements(driver)
        remove_elements = [
            ".imagebar.forpc",  # 顶栏图片
            "#top_nav",  # 顶导航栏
            "#header",  # 页面顶栏
            "#sideBar",  # 页面侧栏
            "#footer",  # 底栏
            "#blog_post_info_block",  # 底部介绍栏
            ".postDesc",  # 文章底部信息栏
            "#comment_form",  # 底部及广告栏
            ".charm-bar-wrapper.hidden"  # 底部广告栏
        ]
        kill_element_by_css_selector(driver, remove_elements)
    

    def bypass_waf(self, url) -> tuple[bool, dict[str, str]]:
        """
        反爬绕过
        :param url: 触发反爬的地址
        :return: (是否成功绕过，通过验证的cookie)
        """
        driver = get_web_driver()
        driver.get(url)

        self.info(f"点击验证码")
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "captcha-button"))
            ).click()
        except Exception as e:
            pass

        self.info(f"拖动滑块验证")

        for i in range(self.try_limit):
            # 确保加载完毕
            start_time = time.time()
            while True:
                text = WebDriverWait(driver, 15).until(
                    EC.visibility_of_element_located((By.ID, "aliyunCaptcha-sliding-text"))
                    ).text.strip()
                if "请拖动滑块完成拼图" in text or time.time() - start_time > 10:
                    break
            
            # 背景图与滑块
            bg_img = driver.find_element(By.ID, "aliyunCaptcha-img").get_attribute("src")
            puzzle_img = driver.find_element(By.ID, "aliyunCaptcha-puzzle").get_attribute("src")

            try:
                bg_img = bg_img.split(",")[1]
                puzzle_img = puzzle_img.split(",")[1]

                bg_img = base64.b64decode(bg_img)
                puzzle_img = base64.b64decode(puzzle_img)
            except IndexError:
                bg_img = requests.get(bg_img, headers=self.headers, cookies=self.cookies).content
                puzzle_img = requests.get(puzzle_img, headers=self.headers, cookies=self.cookies).content
            except Exception as e:
                self.error(f"获取滑块验证码失败：{e}")
                continue
            
            # with open("bg.png", "wb") as f:
            #     f.write(bg_img)

            # with open("puzzle.png", "wb") as f:
            #     f.write(puzzle_img)

            # todo
            # 计算偏移量
            self.info(f"自动滑块验证码待开发，请先手动通过人机验证")

            # 滑块元素
            slide_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.ID, "aliyunCaptcha-sliding-slider"))
            )

            # todo
            # 拖动滑块

            # 验证结果
            while True:
                text = driver.find_element(By.ID, "aliyunCaptcha-sliding-text").text.strip()
                if "请拖动滑块完成拼图" not in text and len(text) > 0:
                    break

            if "验证通过" in text:
                self.info(f"验证成功")
                time.sleep(5)

                # 更新cookie
                cookies = driver.get_cookies()
                self.debug(f"获取cookie：{cookies}")
                for cookie in cookies:
                    if cookie["name"] == "zzk-captcha":
                        self.cookies[cookie["name"]] = cookie["value"]
                        self.info(f"Cookie更新：{cookie['name']}={cookie['value']}")
                        driver.quit()
                        return (True, {cookie["name"]: cookie["value"]})
                self.warn(f"未获取到有效Cookie，重新尝试({i+1}/{self.try_limit})")
            else:
                self.warn(f"验证失败，重新尝试({i+1}/{self.try_limit})")

        driver.quit()  
        return (False,None)

    def search(self, search_dict: dict) -> list[dict]:
        if search_dict.get("keyword", None) is None:
            raise ValueError(f"未获取到输入关键词")

        self.keyword.update(search_dict)
        
        download_event_list = []
        
        for page in range(1, self.MAX_PAGE):
            self.info(f"开始搜索第{page}页")
            params = {
                "Keywords": search_dict["keyword"],
                "ViewCount": search_dict.get("ViewCount", ""),
                "DiggCount": search_dict.get("DiggCount", ""),
                "DateTimeRange": self.time_dict[search_dict.get("DateTimeRange", "不限制")],
                "pageindex": str(page),
            }

            res = requests.get(self.base_url + "/s/blogpost", params=params, headers=self.headers, cookies=self.cookies)
            if "请完成人机验证" in res.text:
                self.info(f"爬虫被拦截，尝试绕过")
                if self.bypass_waf(res.url)[0]:
                    self.info(f"绕过成功")
                    # 重新请求
                    res = requests.get(self.base_url + "/s/blogpost", params=params, headers=self.headers, cookies=self.cookies)
                else:
                    self.error(f"绕过失败，检索终止")
                    break
            
            # 无结果
            if "没有找到您搜索的相关内容" in res.text:
                break
            
            # 信息处理
            soup = BeautifulSoup(res.text, "html.parser")
            divs = soup.find_all("div", class_="searchItem")
            for div in divs:
                a = div.find_all("a")[0]
                new_download_event = {
                    "url": a.get("href"),
                    "title": a.text
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
    cnblogs = CNBlogs()
    cnblogs.search({"keyword": "CVE"})
    cnblogs.download()
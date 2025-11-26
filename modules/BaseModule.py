#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# @Time    : 2025/10/21 下午9:50
# @Author  : BR
# @File    : module.py
# @description: 模块

from abc import ABC, abstractmethod
from pathlib import Path
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.log import log
from utils.tools import get_web_driver, replace_Illegal_characters, kill_element_by_css_selector
from config import CONFIG


def is_page_blank(driver) -> bool:
        """
        检查页面是否“白屏”
        白屏定义：没有可见的文本内容、没有主要容器、documentElement 高度很小
        :param driver:
        :return: 是否为白屏
        """
        try:
            # 方法 1: 获取页面可见文本
            body_text = driver.execute_script("""
                return document.body ? document.body.innerText.trim() : '';
            """)
            if len(body_text) > 10:  # 有足够文本
                return False

            # 方法 2: 检查是否有常见内容容器（根据目标网站调整）
            content_selectors = [
                '.main-content', '.post-body', '.thread-content',
                '.tpc_content', '.article', '.content', 'article',
                '.view-content', '#content'
            ]
            for selector in content_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    # 检查元素是否可见且有一定大小
                    if elem.is_displayed() and (elem.size['height'] > 50 or len(elem.text) > 10):
                        return False
                except:
                    continue

            # 方法 3: 检查页面高度
            doc_height = driver.execute_script("return document.documentElement.scrollHeight;")
            if doc_height < 100:  # 页面高度小于 100px，可能是白屏
                return True

            return True  # 默认认为是白屏（保守策略）

        except Exception as e:
            print(f"检查白屏时出错: {e}")
            return True  # 出错时保守处理：认为是白屏


class BaseModule(ABC):
    def __init__(self, logs: list|None = None):
        """
        param logs: 接入日志记录器
        """
        self.logs = logs if logs is not None else []
        self.base_url = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
        }
        self.base_path = CONFIG["download"]["path"]  # 下载路径
        self.TAG = "BaseModule"  # 日志标识TAG
        self.MAX_PAGE = 9999  # 最大页数

        self.allow_download = True  # 是否允许下载
        self.downloading = False  # 是否是下载中
        self.download_data = {
            "total": 0,
            "completed": 0,
            "data": []
        }  # 下载信息

        self.keyword = {
            "keyword": ""
        }  # 搜索信息

    def info(self, msg: str) -> None:
        self.logs.append(log.info(msg, self.TAG))

    def error(self, msg: str) -> None:
        self.logs.append(log.error(msg, self.TAG))
    
    def warn(self, msg: str) -> None:
        self.logs.append(log.warn(msg, self.TAG))

    def debug(self, msg: str) -> None:
        self.logs.append(log.debug(msg, self.TAG))

    @abstractmethod
    def search(self, search_dict: dict) -> list[dict]:
        pass

    def kill_elements(self, driver) -> None:
        """
        消除无用元素
        :param driver:
        :return:
        """
        pass

    def wait_to_load(self, driver) -> bool:
        """
        等待页面加载完成
        :param driver: webdriver对象
        :return:
        """
        # 等待网页加载完成
        # 白屏额外等待
        try:
            if is_page_blank(driver):
                time.sleep(3)

            WebDriverWait(driver, 300).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except Exception as e:
            return True

        return True

    def download_from_url(self, driver, url, save_path) -> str:
        """
        从指定网站url下载保存文件为.mhtml文件
        :param driver: webdriver对象
        :param url: 目标url
        :param save_path: 文件保存路径
        :return: status: 下载状态：success，fail，skip
        """
        # 路径处理
        file_path = Path(save_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 开始下载网页，并保存为mhtml格式
        self.info(f"开始下载 {url}")
        try:
            driver.get(url)
            # driver.execute_script(f"window.open('{url}')")
        except Exception as e:
            self.error(f"访问 {url} 失败: {e}")
            return "fail"
        
        # 等待页面加载
        if not self.wait_to_load(driver):
            self.warn("未完成加载等待，跳过")
            return "skip"
        self.info(f"{url}页面加载结束")

        # 移除无用元素（节省空间方便查看）
        try:
            self.kill_elements(driver)
        except Exception as e:
            self.debug(f"移除无用元素失败: {e}")

        # 快闪保存(.mhtml)
        try:
            res = driver.execute_cdp_cmd('Page.captureSnapshot', {})
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                f.write(res['data'])
        except Exception as e:
            self.warn(f"保存 {url} 失败: {e}")
            return "fail"

        self.info(f"{url} 下载完成，保存至: {file_path}")
        return "success"

        # if DEBUG:
        #     while True:
        #         pass

    def get_save_path(self, title: str) -> Path:
        """
        获取下载文件保存路径
        :param title: 文章标题
        :return:
        """
        tag = self.TAG.replace("[", "").replace("]", "")
        return (Path(self.base_path) /
                Path(f"{replace_Illegal_characters(self.keyword['keyword'])}_from_{tag}") /
                Path(replace_Illegal_characters(title) + ".mhtml"))
    

    def download(self) -> None:
        """
        根据下载列表使用多线程进行下载
        :param download_event_list: 下载列表
        :return:
        """
        if len(self.download_data["data"]) == 0:
            self.warn(f"没有需要下载的项目")
            return

        try:
            driver = get_web_driver()
        except Exception as e:
            self.error(f"获取浏览器驱动失败: {e}")
            raise Exception(f"获取浏览器驱动失败: {e}")

        while len(self.download_data["data"]) > 0:
            if not self.allow_download:
                self.info(f"主动中断下载")
                driver.quit()
                return

            self.downloading = True  # 下载中

            download_event = self.download_data["data"].pop()
            title = download_event["title"]
            url = download_event["url"]
            save_path = self.get_save_path(title)

            try:
                status = self.download_from_url(driver, url, save_path)
            except Exception as e:
                self.error(f"下载过程中出错：{str(e)}")
                status = "fail"

            self.download_data["completed"] += 1

            download_status = f"当前进度:{self.download_data['completed']}/{self.download_data['total']}"
            if status == "success":
                self.info(f"[{title}]下载完成, {download_status}")
            elif status == "skip":
                self.info(f"[{title}]跳过下载, {download_status}")
            else:
                self.error(f"[{title}]下载失败, {download_status}")
            
            self.downloading = False  # 下载完成
        self.info(f"所有数据下载完毕")

        driver.quit()


if __name__ == "__main__":
    base = BaseModule()
    

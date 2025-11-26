#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# @Time    : 2025/10/16 下午10:57
# @Author  : BR
# @File    : tools.py
# @description: 工具包

import requests
from pathlib import Path
import re
from typing import Union
import threading
import importlib
import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
from config import CONFIG
from utils.log import log

def get_platform():
    return platform.system()

def replace_str_in_binary(file_path: str, old_bytes: bytes, new_bytes: bytes):
    with open(file_path, 'rb') as f:
        data = f.read()

    if old_bytes in data:
        log.info(f"尝试将{file_path}中的{old_bytes}替换为{new_bytes}")
        modified_data = data.replace(old_bytes, new_bytes)

        with open(file_path, 'wb') as f:
            f.write(modified_data)
        log.info(f"替换完成")

def check_internet() -> bool:
    """
    检查网络状态
    :return: 网络是否联通
    """
    try:
        response = requests.get("http://www.baidu.com", timeout=5)
        if 200 <= response.status_code < 400:
            return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        log.error("请检查网络连接是否正常")
        return False
    return False

def get_web_driver(browser="chrome", driver_path=None, show_window=False) -> webdriver:
    """
    初始化浏览器驱动
    :param browser: 浏览器类型，默认使用 Chrome
    :param driver_path: 使用自定义路径，默认为空
    :param show_window: 是否需要展示窗口
    :return:
    """

    if CONFIG["driver"]["use_local_driver"]:
        log.info("使用配置信息对本地浏览器驱动进行初始化")
        browser = CONFIG["driver"]["browser_type"]
        driver_path = CONFIG["driver"]["local_driver_path"]

    if browser == "chrome":
        try:
            if driver_path is None or driver_path == "":
                log.info("正在安装 ChromeDriver...")
                driver_path = Path(ChromeDriverManager().install())
                log.info(f"ChromeDriver 安装成功: {driver_path}")

                driver_dir = driver_path if driver_path.is_dir() else driver_path.parent
                
                if CONFIG["global"]["platform"] == "Windows":
                    driver_path = driver_dir / "chromedriver.exe"
                else:
                    raise Exception(f"暂不支持的平台：{CONFIG['global']['platform']}")

            # 去除cdc_特征
            replace_str_in_binary(driver_path, b"cdc_", b"brh_")

            service = ChromeService(executable_path=str(driver_path))

            options = ChromeOptions()

            # user_data_dir = tempfile.mkdtemp()
            # options.add_argument(f"--user-data-dir={user_data_dir}")
            
            options.add_argument("--no-first-run")
            options.add_argument("--disable-infobars")
            options.add_argument("--start-maximized")
            options.add_experimental_option('useAutomationExtension', False)
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0")
            if not CONFIG["global"]["debug"] and not show_window:
                options.add_argument("--headless")  # 启用无头模式
                options.add_argument("--disable-gpu")  # 禁用 GPU 加速

            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(CONFIG["download"]["timeout"])

            log.info("Chrome 浏览器启动成功")

        except Exception as e:
            log.error(f"Chrome 浏览器初始化失败: {e}")
            raise Exception("无法初始化浏览器，请检查网络或手动安装 ChromeDriver")

    elif browser == "edge":
        # TODO
        raise Exception("暂未开发Edge浏览器支持")

    else:
        raise Exception(f"不支持的浏览器类型: {browser}")

    # 去除特征
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
                     get: () => undefined
                  })
        """
        })

    driver.execute_cdp_cmd("Browser.resetPermissions", {})

    driver.set_page_load_timeout(300)
    return driver

def kill_element_by_css_selector(driver, selectors: list[str]) -> None:
    """
    根据 CSS 选择器删除元素
    :param driver: WebDriver
    :param selectors: CSS 选择器列表
    """
    jscode = """
        (function(sels){
        sels.forEach(function(s){
            try {
            var nodes = document.querySelectorAll(s);
            nodes.forEach(function(n){ try{ n.remove(); } catch(e){ n.style.display='none'; } });
            } catch(e){}
        });
        })(arguments[0]);
    """
    try:
        driver.execute_script(jscode, selectors)
    except Exception as e:
        log.warn(f"删除元素失败: {e}")

def replace_Illegal_characters(input_str: str, replace_char='_') -> str:
    """
    替换非法字符
    :param input_str: 待处理字符串
    :param replace_char: 将非法字符替换为指定合法字符，默认替换为_
    :return:
    """
    return re.sub(r'[<>:"/\\|?*\n\r\t\f\v\0]', replace_char, input_str)

def get_class_from_string(class_path) -> object:
    """
    根据字符串获取类
    :param class_path: 类路径，例如 'utils.log.log'
    :return: 类对象
    """
    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls

def count_workers_by_prefix(prefix: str) -> int:
    """
    根据前缀获取当前运行的线程数量
    """
    return sum(
        1 for t in threading.enumerate()
        if t.name.startswith(prefix)
    )

def is_dir_exists(path: Union[str, Path]) -> bool:
    """
    判断指定路径是否为一个存在的目录。
    """
    if not Path(path).exists():
        return False
    
    if Path(path).is_file():
        return Path(path).parent.exists()
    
    return Path(path).is_dir()


def is_file_exists(path: Union[str, Path]) -> bool:
    """
    判断指定路径是否为一个存在的文件。
    """
    return Path(path).exists() and Path(path).is_file()
    


if __name__ == "__main__":
    pass

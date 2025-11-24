import binascii
import requests
from bs4 import BeautifulSoup

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tools import kill_element_by_css_selector
from modules import BaseModule


def str2hex(input_str) -> str:
    """
    字符串按指定格式转16进制
    :param input_str:
    :return:
    """
    str0x = binascii.hexlify(input_str.encode('utf-8')).decode('utf-8')
    search_data = ""
    for i in range(0, len(str0x), 2):
        search_data += f"_{str0x[i:i + 2]}"  # 字符串转16进制,并添加_
    return search_data

class KanXue(BaseModule):
    def __init__(self, logs: list|None = None):
        super().__init__(logs)
        self.base_url = "https://bbs.kanxue.com"
        self.TAG = "看雪"
        self.keyword = {
            "keyword": ""  # 搜索关键字
        }

    
    def kill_elements(self, driver) -> None:
        super().kill_elements(driver)
        remove_elements = [
            ".position-fixed.text-center.collection_thumb_left",  # 左侧栏
            ".card.p-1",  # 回复
            ".btn.btn-secondary.btn-block.xn-back.my-3.mx-auto",  # 返回按钮
            ".col-lg-3.pr-0.hidden-sm.hidden-md",  # 右侧栏
            "#header",  # 顶部栏
            ".breadcrumb.mb-3.py-0.small.px-0",  # 顶部横条
            ".container.px-0.pb-3.bbs_footer_start_column",  # 底部广告栏
            "#collection_thumb",  # 文章底部赞赏
            ".bbs_thread",  # 文章底部；链接
            "#footer"  # 底部栏
            ]
        kill_element_by_css_selector(driver, remove_elements)
    

    def search(self, search_dict: dict) -> dict:
        """
        通过关键词查询获取待下载列表
        :param search_dict: 查询关键词
        :return:
        """
        if search_dict.get("keyword", None) is None:
            raise ValueError(f"未获取到输入关键词")
        
        self.keyword.update(search_dict)
        
        download_event_list = []

        self.info(f"开始搜索关键词{search_dict}相关帖子")
        for i in range(1, self.MAX_PAGE):
            self.info(f"开始搜索第{i}页")
            search_url = self.base_url + f"/search-{str2hex(search_dict['keyword'])}-1-{str(i)}.htm"
            res = requests.get(search_url, headers=self.headers).text

            soup = BeautifulSoup(res, "html.parser")

            # 先通过<div class="card-body">的最后一个元素获取帖子列表
            pages_div = soup.find_all("div", class_="card-body")[-1]
            if "无结果" in pages_div.text:
                break

            # 进一步过滤筛选获得<a href="thread-288195.htm" style="vertical-align: middle;">[分享] unidbg 反检测内存地址截断排错记录</a>
            pages_a = pages_div.find_all("a", style="vertical-align: middle;")
            pages_a = [page_a for page_a in pages_a if page_a.get('target') is None]

            # 构建待下载列表
            for page_a in pages_a:
                new_download_event = {
                    "url": self.base_url + "/" + page_a.get("href"),
                    "title": page_a.text
                }
                download_event_list.append(new_download_event)
        self.info(f"关键词 {search_dict['keyword']} 共检索到{len(download_event_list)}条下载数据")
        
        self.download_data = {
            "total": len(download_event_list),
            "completed": 0,
            "data": download_event_list
        }
        return self.download_data

if __name__ == '__main__':
    kx = KanXue()
    kx.search({"keyword": "unidbg"})
    kx.download()
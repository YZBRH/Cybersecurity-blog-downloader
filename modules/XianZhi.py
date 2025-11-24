import requests
import codecs
import urllib.parse
import json
import re
from bs4 import BeautifulSoup

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tools import kill_element_by_css_selector
from modules import BaseModule


def extract_makeview_body(html_text: str) -> str:
    key = "makeView('markdown-body'"
    idx = html_text.find(key)
    if idx == -1:

        raise ValueError("makeView('markdown-body', ...) not found")
    first_quote = html_text.find('"', idx)
    if first_quote == -1:
        raise ValueError('opening quote not found after makeView')
    i = first_quote + 1
    buf = []
    escaped = False
    while i < len(html_text):
        ch = html_text[i]
        if ch == '"' and not escaped:
            break
        buf.append(ch)
        if ch == '\\':
            escaped = not escaped
        else:
            escaped = False
        i += 1
    literal = ''.join(buf)
    decoded = codecs.decode(literal, 'unicode_escape')
    decoded = decoded.replace('\\/', '/')
    return decoded

def make_img_tag(soup, src, width=None, height=None, alt=''):
    wrapper = soup.new_tag('div')
    wrapper['class'] = 'yuque-img-wrap'
    wrapper['style'] = 'max-width:100%; overflow:visible; text-align:center;'
    img = soup.new_tag('img')
    img['src'] = src
    img['style'] = 'display:block; margin:0 auto; max-width:100%; height:auto; object-fit:contain;'
    if alt:
        img['alt'] = alt
    if width:
        try:
            img['width'] = str(int(width))
        except Exception:
            pass
    if height:
        try:
            img['height'] = str(int(height))
        except Exception:
            pass
    wrapper.append(img)
    return wrapper

def convert_fragment(fragment_html: str) -> str:
    """
    转换片段：代码块卡、图像卡、背景图像元素。
    返回完整片段 HTML（字符串）。
    """
    soup = BeautifulSoup(fragment_html, 'html.parser')

    # 代码块
    for card in soup.find_all('card', attrs={'name': 'codeblock'}):
        val = card.get('value', '')
        if not val:
            card.decompose()
            continue
        if val.startswith('data:'):
            data_str = val[len('data:'):]
        else:
            data_str = val
        try:
            json_str = urllib.parse.unquote(data_str)
            obj = json.loads(json_str)
            code_text = obj.get('code', '')
            mode = obj.get('mode', '') or obj.get('language', '')
        except Exception:
            code_text = ''
            mode = ''
        pre = soup.new_tag('pre')
        code_tag = soup.new_tag('code')
        if mode:
            code_tag['class'] = [f'language-{mode}']

        code_tag.string = code_text
        pre.append(code_tag)
        card.replace_with(pre)

    # 图片
    for card in soup.find_all('card', attrs={'name': 'image'}):
        val = card.get('value', '')
        if not val:
            card.decompose()
            continue
        if val.startswith('data:'):
            data_str = val[len('data:'):]
        else:
            data_str = val
        try:
            json_str = urllib.parse.unquote(data_str)
            obj = json.loads(json_str)
            src = obj.get('src') or obj.get('url') or ''
            width = obj.get('width')
            height = obj.get('height')
            alt = obj.get('name') or obj.get('alt') or ''
        except Exception:
            src = ''
            width = None
            height = None
            alt = ''
        if not src:
            card.decompose()
            continue
        new_wrapper = make_img_tag(soup, src, width=width, height=height, alt=alt)
        card.replace_with(new_wrapper)

    # BACKGROUND-IMAGE -> img
    for el in soup.find_all(lambda t: t.has_attr('style') and 'background' in t['style'].lower()):
        style = el['style']
        
        m = re.compile(r'url\((?:["\']?)(.*?)(?:["\']?)\)', flags=re.I).search(style)
        if not m:
            continue
        bg_url = m.group(1).strip()
        if not bg_url:
            continue
        # 构建替换img包装器
        new_wrapper = make_img_tag(soup, bg_url, alt=el.get('alt', '') or '')
        el.replace_with(new_wrapper)

    # CLEANUP：移除 overflow：hidden 和固定高度以避免裁剪
    for node in soup.find_all(True):
        style = node.get('style', '')
        if not style:
            continue
        new_style = style
        new_style = re.sub(r'overflow\s*:\s*hidden\s*;?', 'overflow:visible;', new_style, flags=re.I)
        new_style = re.sub(r'height\s*:\s*\d+px\s*;?', '', new_style, flags=re.I)
        new_style = new_style.strip().strip(';')
        if new_style:
            node['style'] = new_style
        else:
            if node.has_attr('style'):
                del node['style']

    return str(soup)


def convert_yuque_page_to_static(html_text: str) -> str:
    """
    返回完整的静态 HTML 文本：替换为 #markdown 体的原始文档
    通过转换后的片段。将删除将重新渲染的脚本。
    """
    fragment = extract_makeview_body(html_text)
    fragment_static = convert_fragment(fragment)

    doc_soup = BeautifulSoup(html_text, 'html.parser')
    container = doc_soup.find(id='markdown-body')
    if container is None:
        minimal = f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>{fragment_static}</body></html>"
        return minimal

    container.clear()
    # 一次追加整个片段树以避免节点丢失
    container.append(BeautifulSoup(fragment_static, 'html.parser'))

    # 删除与 yuque 相关的动态脚本
    for s in doc_soup.find_all('script'):
        src = s.get('src', '') or ''
        txt = s.string or ''
        if 'doc.umd.js' in src or '/assets/js/yuque/' in src or "makeView('markdown-body'" in txt:
            s.decompose()

    head = doc_soup.head
    if head:
        style_tag = doc_soup.new_tag('style')
        style_tag.string = """
            pre { background: #f6f8fa; padding: 12px; overflow:auto; border-radius:6px; }
            code { font-family: SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace; white-space: pre; }
            .yuque-img-wrap { margin: 0.9em 0; }
        """
        head.append(style_tag)

    return str(doc_soup)

def replace_yuque_page_to_static(driver) -> None:
    html = driver.page_source
    static_html = convert_yuque_page_to_static(html)

    # 写回浏览器
    driver.execute_script("document.open(); document.write(arguments[0]); document.close();", static_html)

    # 内联图片
    driver.set_script_timeout(60)
    jscode = """
        const callback = arguments[arguments.length-1];
        (async function(){
        try {
            const imgs = Array.from(document.querySelectorAll('img'));
            for (let img of imgs) {
            try {
                if (!img.complete) {
                await new Promise(r => { img.onload = r; img.onerror = r; });
                }
                // create canvas
                const w = img.naturalWidth || img.width || 1;
                const h = img.naturalHeight || img.height || 1;
                const canvas = document.createElement('canvas');
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);
                // toDataURL may fail for cross-origin images unless CORS allows it.
                try {
                const dataUrl = canvas.toDataURL('image/png');
                img.src = dataUrl;
                } catch(e) {
                // skip if cross-origin blocks canvas read; leave original src
                console.warn('inline failed', e);
                }
            } catch(e) {
                console.warn('img inline catch', e);
            }
            }
            callback(true);
        } catch(e) {
            callback(false);
        }
        })();
    """
    driver.execute_async_script(jscode)


class XianZhi(BaseModule):
    def __init__(self, logs : list|None = None):
        super().__init__(logs)
        self.base_url = "https://xz.aliyun.com"
        self.TAG = "先知社区"
        self.keyword = {
            "keyword": "",  # 搜索关键词(必选)
        }

    def kill_elements(self, driver):
        super().kill_elements(driver)
        selectors = [
            ".nav.nav_border",  # 顶部导航栏
            ".right_extras",  # 右侧悬浮栏
            ".right_container",  # 右侧栏
            ".detail_share.mt20",  # 文章底栏
            ".detail_comment.comment_box_quill",  # 评论栏
            ".footer.pd20",  # 底栏
            ".loading"  # 加载动画
        ]
        kill_element_by_css_selector(driver, selectors)


    def wait_to_load(self, driver) -> bool:
        if not super().wait_to_load(driver):
            return False
        
        try:
            replace_yuque_page_to_static(driver)
        except Exception as e:
            pass

        return True

    def search(self, search_dict: dict) -> dict:
        if search_dict.get("keyword", None) is None:
            raise ValueError(f"未获取到输入关键词")
        
        self.keyword.update(search_dict)
        
        params = {
            "keywords": search_dict["keyword"],
            "page": "1",
            "limit": "99",
            "type": "3"
        }
        res = requests.get(self.base_url + "/search/data", params=params, headers=self.headers)
        res_json = json.loads(res.text)
        
        if not res_json.get("status", False):
            self.error(f"检索失败！获得数据：{res_json.get('data', '')}")
            return
        
        if int(res_json.get("count", 0)) == 0:
            self.info(f"没有检索到数据！")
            return
        
        data = res_json.get("data", "")
        soup = BeautifulSoup(data, "html.parser")
        as_ = soup.find_all("a", class_="news_title")
        download_event_list = []
        for a in as_:
            new_download_event = {
                    "url": a.get("href"),
                    "title": a.text.strip()
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
    xianzhi = XianZhi()
    xianzhi.search({"keyword": "CVE"})
    xianzhi.download()
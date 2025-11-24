from flask import Flask, render_template, request, jsonify, url_for, redirect, Response
import threading
import time
import json
import os
import tkinter as tk
from tkinter import filedialog

from utils.tools import get_class_from_string, count_workers_by_prefix, is_file_exists, is_dir_exists
from utils.log import log
from modules import BaseModule
from config import CONFIG

app = Flask(__name__)

with open("./config/modules_template.json", "r", encoding="utf-8") as fp:
    MODULE_TEMPLATE : dict[str, dict] = json.load(fp)

with open("./config/config_template.json", "r", encoding="utf-8") as fp:
    CONFIG_TEMPLATE : dict[str, dict] = json.load(fp)

class BaseTask:
    def __init__(self, task_id):
        self.task_id : str = task_id
        self.status : str = "running"
        self.start_time : float = time.time()
        self.logs : list = []
        self.TAG : str = "BaseTask"

    def info(self, msg):
        self.logs.append(log.info(msg, self.TAG))
    
    def error(self, msg):
        self.logs.append(log.error(msg, self.TAG))
    
    def warn(self, msg):
        self.logs.append(log.warn(msg, self.TAG))

class SearchTask(BaseTask):
    def __init__(self, task_id, module_key: str, params: dict):
        super().__init__(task_id)
        self.start_time : float = time.time()
        self.TAG : str = "Search"
        self.module_key = module_key
        self.params = params

    def __eq__(self, other):
        return self.module_key == other.module_key and self.params == other.params

class DownloadTask(BaseTask):
    def __init__(self, task_id: str, name: str, module: BaseModule):
        super().__init__(task_id)
        self.start_time : float = time.time()
        self.end_time : float = time.time()
        self.TAG : str = "Download"
        self.status : str = "pending"  # waiting, pending, pausing, paused, done, error, running
        self.name : str = name
        self.module : BaseModule = module
        self.logs = module.logs

    def get_info(self):
        if self.status in ["pausing", "running"]:
            self.end_time = time.time()

        return{
            "id": self.task_id,
            "speed_time": round(self.end_time - self.start_time, 2),
            "name": self.name,
            "status": self.status,
            "start_time": self.start_time,
            "download_data": self.module.download_data
        }
    
    def set_allow_download_status(self, status: bool):
        self.module.allow_download = status
    
    def is_downloading(self):
        return self.module.downloading

    def is_allow_download(self):
        return self.module.allow_download
    
    def run(self):
        self.set_allow_download_status(True)
        try:
            self.module.download()
        except Exception as e:
            self.set_allow_download_status(False)
            self.status = "error"
            self.error(f"下载任务 {self.task_id} 出现错误：{e}")

    def is_completed(self):
        return self.module.download_data["completed"] == self.module.download_data["total"]

    
global SEARCH_TASKS, DOWNLOAD_TASKS
SEARCH_TASKS : dict[str, SearchTask] = {} # 全局存储搜索信息
DOWNLOAD_TASKS : dict[str, DownloadTask] = {} # 全局存储下载信息

def is_have_same_search_task(search_task: SearchTask) -> tuple[bool, SearchTask]:
    """
    判断是否已存在相同的搜索任务
    """
    for task_id in SEARCH_TASKS.keys():
        if SEARCH_TASKS[task_id] == search_task:
            return True, SEARCH_TASKS[task_id]
    return False, None


def search_task(task_id, module_key, params):
    """
    搜索任务函数
    """
    search_task = SearchTask(task_id, module_key, params)

    check, tmp_search_task = is_have_same_search_task(search_task)
    if check:
        tmp_search_task.warn("已存在相同的搜索任务，将不会重复执行")
        return

    SEARCH_TASKS[task_id] = search_task
    
    try:
        if module_key not in MODULE_TEMPLATE.keys():
            raise Exception(f"未注册的模块: {module_key}")

        search_task.info(f"开始执行模块: {MODULE_TEMPLATE[module_key]['name']}, 参数: {params}")
        time.sleep(0.5)
        
        try:
            ModuleClass = get_class_from_string(f"modules.{module_key}")
            module_class = ModuleClass(search_task.logs)
        except Exception as e:
            raise Exception(f"载入模块 {module_key} 时出错: {e}")

        try:
            module_class.search(params)
        except Exception as e:
            raise Exception(f"模块 {module_key} 查询时出错: {e}")
        
        task_id = task_id.replace("search", "download")  # 搜索任务转化为下载任务
        download_task = DownloadTask(task_id, 
                                         MODULE_TEMPLATE[module_key]['name'] + "-" + params["keyword"], 
                                         module_class)
        DOWNLOAD_TASKS[task_id] = download_task
        download_task.info(f"新增下载任务：{download_task.name}")
        
        search_task.info("搜索完成！")
        search_task.status = "done"
    except Exception as e:
        search_task.error(f"任务异常: {str(e)}")
        search_task.status = "error"

def cleanup_search_tasks():
    """
    清理超过 MAX_TASK_DURATION（如 600 秒）仍未结束的任务
    """
    MAX_TASK_DURATION = 60000
    while True:
        time.sleep(60)  # 每分钟检查一次
        now = time.time()
        stale_ids = []
        for tid in list(SEARCH_TASKS.keys()):
            task = SEARCH_TASKS.get(tid, None)
            if task is None:
                continue

            if task.status != "done" and (now - task.start_time) > MAX_TASK_DURATION:
                stale_ids.append(tid)
        
        for tid in stale_ids:
            task.warn(f"Force-cleaning stale task: {tid}")
            SEARCH_TASKS.pop(tid, None)

threading.Thread(target=cleanup_search_tasks, daemon=True, name="clearer").start()

def check_download_task():
    """
    持续监测下载进程
    """
    lock = threading.Lock()
    download_thread_prefix = "download-"

    while True:
        for task_id in list(DOWNLOAD_TASKS.keys()):
            task = DOWNLOAD_TASKS[task_id]

            if task is None:
                continue

            if task.status in ["waiting"] and count_workers_by_prefix(download_thread_prefix) < CONFIG["download"]["max_workers"]:
                # 有待下载的任务且有空余线程则开始下载
                log.info(f"下载线程: download-{task_id} 启动，当前在线线程：{count_workers_by_prefix(download_thread_prefix)}")
                threading.Thread(target=task.run, name=f"download-{task_id}").start()
                task.status = "running"
            
            if task.status in ["pausing"] and task.is_downloading() and task.is_allow_download():
                # 暂停任务
                task.set_allow_download_status(False)

            if task.status in ["pausing"] and not task.is_downloading():
                # 暂停完毕，更新显示状态
                task.status = "paused"

            if task.is_completed():
                task.status = "done"

threading.Thread(target=check_download_task, daemon=True, name="download_checker").start()

@app.route('/')
def index():
    return redirect(url_for('search_page'))

@app.route('/search', methods=["GET", 'POST'])
def search_page():
    """
    search页
    """
    if request.method == "GET":
        # 首次启动若配置有误提示跳转到配置页
        if CONFIG["driver"]["use_local_driver"] and not is_file_exists(CONFIG["driver"]["local_driver_path"]):
            return "<html><script>alert('当前配置强制启用了本地驱动，但程序未找到本地驱动文件，请重新配置！');window.location.href='/setting'</script>/html>"
        return render_template('search.html', modules=MODULE_TEMPLATE)
    
    data = request.get_json()
    module_key = data.get('module')
    params = data.get('params', {})
    
    if module_key not in MODULE_TEMPLATE:
        return jsonify({"status": "error", "log": "Invalid module"}), 400

    keys = []
    task_ids = []
    if module_key == "ALL":
        # 如果是ALL模块，则遍历除了ALL以外的所有模块
        keys = list(MODULE_TEMPLATE.keys()).copy()
        print(keys)
        keys.remove("ALL")
    else:
        keys.append(module_key)
        
    for m_key in keys:
        # 新建任务
        task_id = f"search_task_{int(time.time() * 1000)}"
        thread = threading.Thread(target=search_task, args=(task_id, m_key, params), name=f"search-{task_id}")
        thread.start()
        task_ids.append(task_id)
        time.sleep(0.5)
    
    return jsonify({"status": "started", "task_ids": task_ids,"modules": keys})

@app.route('/search/log_stream/<task_id>')
def search_log_stream(task_id):
    """
    search日志流
    """
    def generate():
        logs_sent = 0
        task = SEARCH_TASKS.get(task_id, None)
        if task is None:
            return

        while True:
            current_logs = task.logs

            while logs_sent < len(current_logs):
                line = current_logs[logs_sent]
                yield f"data: {json.dumps({'line': line})}\n\n"
                logs_sent += 1
            
            if task.status == "done":
                yield f"data: {json.dumps({'line': task.info(f'[Search] {task_id} 任务结束'), 'done': True})}\n\n"
                break
            
            time.sleep(0.3)
        
        SEARCH_TASKS.pop(task_id, None)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download')
def download_page():
    # 首次启动若配置有误提示跳转到配置页
    if CONFIG["driver"]["use_local_driver"] and not is_file_exists(CONFIG["driver"]["local_driver_path"]):
        return "<html><script>alert('当前配置强制启用了本地驱动，但程序未找到本地驱动文件，请重新配置！');window.location.href='/setting'</script>/html>"
    return render_template('download.html')

@app.route('/download/tasks', methods=['GET'])
def get_tasks():
    """
    获取下载任务
    """
    tasks_info = []
    for t in list(DOWNLOAD_TASKS.keys()):
        task = DOWNLOAD_TASKS.get(t, None)
        if task is None:
            continue
        tasks_info.append(task.get_info())
    return jsonify(tasks_info)

@app.route('/download/log_stream/<task_id>')
def download_log_stream(task_id):
    """
    download日志流
    """
    def generate():
        logs_sent = 0
        task = DOWNLOAD_TASKS.get(task_id, None)
        if task is None:
            return

        while True:
            current_logs = task.logs

            while logs_sent < len(current_logs):
                line = current_logs[logs_sent]
                yield f"data: {json.dumps({'line': line})}\n\n"
                logs_sent += 1
            
            if task.status == "done":
                yield f"data: {json.dumps({'line': task.info(f'[download] {task_id} 任务结束'), 'done': True})}\n\n"
                break
            
            time.sleep(0.3)
        
        # DOWNLOAD_TASKS.pop(task_id, None)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/start', methods=['POST'])
def start_download_task():
    """
    启动下载任务
    """
    data = request.get_json()
    task_id = data.get('id')
    task = DOWNLOAD_TASKS.get(task_id, None)
    if task is None:
        return jsonify({"status": "error", "message": "Task not found"}), 404
    
    if task.status in ['pending', 'paused']:
        task.status = 'waiting'
        return jsonify({"status": "success", "task": task_id}), 200
    
    if task.status in ['pausing', 'running']:
        return jsonify({"status": "error", "message": "Task is being paused. Please wait."}), 400
    
    if task.status in ['waiting']:
        return jsonify({"status": "error", "message": "Task is already waiting to start"}), 400
    
    return jsonify({"status": "error", "message": "Unknown error"}), 500


@app.route('/download/pause', methods=['POST'])
def pause_download_task():
    data = request.get_json()
    task_id = data.get('id')
    task = DOWNLOAD_TASKS.get(task_id, None)

    if task is None:
        return jsonify({"status": "error", "message": "Task not found"}), 404
    
    if task.status in ["running", "waiting"]:
        task.status = "pausing"
        return jsonify({"status": "success", "task": task_id}), 200
    
    return jsonify({"status": "error", "message": "Task is not running or waiting"}), 400

@app.route('/download/delete', methods=['POST'])
def delete_download_task():
    data = request.get_json()
    task_id = data.get('id')
    task = DOWNLOAD_TASKS.get(task_id, None)
    if task is None:
        return jsonify({"status": "error", "message": "Task not found"}), 404
    
    if task.status in ["running", "pausing"]:
        return jsonify({"status": "error", "message": "Cannot delete a task that is running."}), 400
    
    check = DOWNLOAD_TASKS.pop(task_id, None)
    if check is None:
        return jsonify({"status": "error", "message": "Task not found"}), 404

    return jsonify({"status": "success", "task": task_id}), 200

@app.route('/download/start_all', methods=['POST'])
def start_all_tasks():
    for t in list(DOWNLOAD_TASKS.keys()):
        task = DOWNLOAD_TASKS[t]
        if task is None:
            continue

        if task.status in ['pending', 'paused']:
            task.status = 'waiting'

    return jsonify({"status": "success"}), 200

@app.route('/download/pause_all', methods=['POST'])
def pause_all_tasks():
    for t in list(DOWNLOAD_TASKS.keys()):
        task = DOWNLOAD_TASKS[t]

        if task is None:
            continue

        if task.status in ['waiting', 'running']:
            task.status = 'pausing'
    return jsonify({"status": "success"}), 200

@app.route('/download/delete_all', methods=['POST'])
def delete_all_tasks():
    for t in list(DOWNLOAD_TASKS.keys()):
        task = DOWNLOAD_TASKS[t]
        if task is None:
            continue

        if task.status in ['running', 'pausing']:
            continue

        check = DOWNLOAD_TASKS.pop(t, None)
        if check is None:
            # delete failed
            log.error(f"delete task {t} failed")

    return jsonify({"status": "success"}), 200

@app.route('/download/delete_completed', methods=['GET'])
def delete_completed_all_tasks():
    for task_id in list(DOWNLOAD_TASKS.keys()):
        task = DOWNLOAD_TASKS[task_id]
        if task.status == "done":
            check = DOWNLOAD_TASKS.pop(task_id, None)
            if check is None:
                log.error(f"delete task {task_id} failed")
                
    return jsonify({"status": "success"}), 200

@app.route('/setting')
def setting_page():
    return render_template('setting.html')

@app.route('/api/settings/config')
def get_setting_config():
    """获取完整的设置配置结构"""
    config_structure = CONFIG_TEMPLATE
    return jsonify(config_structure)

@app.route('/api/settings/<category>', methods=['GET', 'POST'])
def category_settings(category):
    """
    获取或者更新指定分类的设置
    """
    # get
    if request.method == "GET":
        try:
            settings = CONFIG.get(category, None)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
        if settings is None:
            return jsonify({'error': f'未知的设置分类: {category}'}), 404
        
        return jsonify({'settings': settings})

    # post
    try:
        data = request.get_json()
        
        # 验证分类是否存在
        config_structure = get_setting_config().get_json()
        category_config = config_structure.get(category, None)
        if category_config is None:
            return jsonify({'status': 'error', 'message': f'未知的设置分类: {category}'}), 404
        
        updated_settings = {}
        
        # 验证和更新每个参数
        for param_config in category_config['params']:
            param_name = param_config['param']
            
            # 跳过只读参数
            if not param_config.get('editable', True):
                continue
                
            # 检查参数是否在请求数据中
            if param_name in data:
                # 验证参数值
                value = data[param_name]
                param_type = param_config.get('type', 'text')
                
                # 类型验证
                if param_type == 'number':
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        return jsonify({'status': 'error', 'message': f'参数 "{param_config["name"]}" 必须是有效数字'}), 400
                    
                    # 范围验证
                    if 'min' in param_config and value < param_config['min']:
                        return jsonify({'status': 'error', 'message': f'参数 "{param_config["name"]}" 不能小于 {param_config["min"]}'}), 400
                    
                    if 'max' in param_config and value > param_config['max']:
                        return jsonify({
                            'status': 'error', 'message': f'参数 "{param_config["name"]}" 不能大于 {param_config["max"]}'}), 400
                    
                
                elif param_type == 'switch':
                    try:
                        value = bool(value)
                    except ValueError:
                        return jsonify({
                            'status': 'error', 'message': f'参数 "{param_config["name"]}" 必须是布尔值'}), 400
                
                elif param_type == 'select':
                    options = [opt['value'] if isinstance(opt, dict) else opt for opt in param_config.get('options', [])]
                    if value not in options:
                        return jsonify({'status': 'error','message': f'参数 "{param_config["name"]}" 必须是有效的选项'}), 400     
                
                elif param_type == 'file':
                    if not is_file_exists(value):
                        return jsonify({'status': 'error', 'message': f'文件 "{value}" 不存在！'}), 400
                    
                elif param_type == 'path':
                    if not is_dir_exists(value):
                        return jsonify({'status': 'error', 'message': f'文件 "{value}" 不存在！'}), 400
                              
                updated_settings[param_name] = value

        try:
            CONFIG.update({category: updated_settings})
        except Exception as e:
            return jsonify({
                'status': 'error', 'message': f'保存失败: {e}'}), 500
        
        return jsonify({
                'status': 'success', 'message': '设置保存成功'})
               
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/settings/<category>/reset', methods=['POST'])
def reset_category_settings(category):
    """
    重置指定分类为默认设置
    """
    try:
        # 验证分类是否存在
        config_structure = get_setting_config().get_json()
        category_config = config_structure.get(category, None)
        if category_config is None:
            return jsonify({'status': 'error', 'message': f'未知的设置分类: {category}'}), 404
        
        # 获取默认设置
        default_settings = {}
        for param_config in category_config['params']:
            if param_config.get('editable', True):  # 只重置可编辑参数
                default_settings[param_config['param']] = param_config['default']
        
        try:
            CONFIG.update({category: default_settings})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'恢复默认设置失败: {e}'}), 500

        return jsonify({'status': 'success', 'message': '已恢复默认设置'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, port=5555)
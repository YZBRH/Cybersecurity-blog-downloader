#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# @Time    : 2025/10/16 下午10:54
# @Author  : BR
# @File    : log.py
# @description: 日志模块

import logging
import time

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CONFIG

# 存储最近的日志条目（内存中）
_recent_logs: list[str] = []

# 创建专用 logger
logger = logging.getLogger("CustomLogger")
logger.setLevel(logging.DEBUG)

def format(record: logging.LogRecord, tag: str) -> str:
    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))

    levelname = record.levelname
    if levelname == "WARNING":
        levelname = "WARN"

    msg = record.getMessage().strip()

    return f"[{time_str}][{levelname}][{tag}] {msg}"

# 防止重复添加处理器（在模块重载或多次导入时）
if not logger.handlers:

    class RecentFileHandler:
        """自定义文件处理器：只保留最新的 N 条日志写入文件"""
        def __init__(self, filename: str, max_lines: int, encoding: str = 'utf-8'):
            self.filename = filename
            self.max_lines = max_lines
            self.encoding = encoding
            self.lock = False  # 防止递归调用

        def emit(self, record: logging.LogRecord, tag: str):
            if self.lock:
                return
            try:
                self.lock = True

                if not CONFIG["log"]["is_save"]:
                    return

                # 格式化日志
                log_entry = format(record, tag)
                # 添加到内存列表
                _recent_logs.append(log_entry + "\r\n")
                # 只保留最新的 max_lines 条
                if len(_recent_logs) > self.max_lines:
                    del _recent_logs[:-self.max_lines]  # 保留末尾 N 条

                # 覆盖写入文件
                try:
                    with open(self.filename, 'w', encoding=self.encoding) as f:
                        f.writelines(_recent_logs)
                except (OSError, IOError) as e:
                    print(f"[ERROR] 无法写入日志文件 {self.filename}: {e}")

            except Exception as e:
                print(f"[ERROR] 日志处理失败: {e}")
            finally:
                self.lock = False


    class ColoredConsoleHandler:
        """控制台输出处理器（带颜色）"""
        COLORS = {
            'INFO': '\033[0m',    # 默认颜色
            'WARN': '\033[33m',   # 黄色
            'ERROR': '\033[31m',  # 红色
            'DEBUG': '\033[34m',   # 蓝色
        }
        RESET = '\033[0m'

        def __init__(self):
            self.lock = False

        def emit(self, record: logging.LogRecord, tag: str) -> str:
            if self.lock:
                return
            try:
                self.lock = True
                formatted_msg = format(record, tag)
                color = self.COLORS.get(record.levelname, self.COLORS['INFO'])
                print(f"{color}{formatted_msg}{self.RESET}")
                return formatted_msg
            finally:
                self.lock = False


    # 实例化处理器
    file_handler = RecentFileHandler(CONFIG['log']['path'], CONFIG['log']['max_lines'], CONFIG['log']['encoding'])
    console_handler = ColoredConsoleHandler()


class log:
    @staticmethod
    def info(msg: str, tag: str = "SYSTEM") -> str:
        """信息日志"""
        record = logger.makeRecord(logger.name, logging.INFO, fn="", lno=0, msg=msg, args=None, exc_info=None)
        # 手动触发两个 handler
        msg = console_handler.emit(record, tag)
        file_handler.emit(record, tag)
        return msg

    @staticmethod
    def warn(msg: str, tag: str = "SYSTEM") -> str:
        """警告日志"""
        record = logger.makeRecord(logger.name, logging.WARN, fn="", lno=0, msg=msg, args=None, exc_info=None)
        msg = console_handler.emit(record, tag)
        file_handler.emit(record, tag)
        return msg

    @staticmethod
    def error(msg: str, tag: str = "SYSTEM") -> str:
        """错误日志"""
        record = logger.makeRecord(logger.name, logging.ERROR, fn="", lno=0, msg=msg, args=None, exc_info=None)
        msg = console_handler.emit(record, tag)
        file_handler.emit(record, tag)
        return msg

    @staticmethod
    def debug(msg: str, tag: str = "SYSTEM") -> str:
        """调试日志"""
        record = logger.makeRecord(logger.name, logging.DEBUG, fn="", lno=0, msg=msg, args=None, exc_info=None)
        # 手动触发两个 handler
        msg = console_handler.emit(record, tag)
        file_handler.emit(record, tag)
        return msg

if __name__ == "__main__":
    log.info("这是一个Info", "TEST")
    log.warn("这是一个Warning", "TEST")
    log.error("这是一个Error", "TEST")
    for i in range(5):
        log.info(f"测试日志 {i+1}")
    print(f"日志已写入 {CONFIG['log']['path']}，仅保留最新 {CONFIG['log']['max_lines']} 条。")

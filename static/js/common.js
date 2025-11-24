// common.js - 公共JavaScript功能

const LOG_STORAGE_KEY_PREFIX = 'appLog_';
const MAX_LOG_LINES = 100;

class LogManager {
    constructor(appName) {
        this.storageKey = LOG_STORAGE_KEY_PREFIX + appName;
        this.appName = appName;
        this.consoleElement = document.getElementById('consoleLog');
        this.loadPersistedLog();
    }

    colorizeLogLine(line) {
        // 添加空值检查
        if (line === null || line === undefined) {
            return `<span class="log-default">[NULL]</span>`;
        }

        const trimmed = line.toString().trim(); // 确保转换为字符串
        if (trimmed.startsWith('[ERROR]') || trimmed.includes('[ERROR]')) {
            return `<span class="log-error">${line}</span>`;
        } else if (trimmed.startsWith('[WARN]') || trimmed.includes('[WARN]')) {
            return `<span class="log-warn">${line}</span>`;
        } else if (trimmed.startsWith('[DEBUG]') || trimmed.includes('[DEBUG]')) {
            return `<span class="log-debug">${line}</span>`;
        } else if (trimmed.startsWith('[INFO]') || trimmed.includes('[INFO]')) {
            return `<span class="log-info">${line}</span>`;
        } else {
            return `<span class="log-default">${line}</span>`;
        }
    }

    loadPersistedLog() {
        const saved = localStorage.getItem(this.storageKey);
        if (saved) {
            try {
                const logs = JSON.parse(saved);
                if (Array.isArray(logs) && logs.length > 0) {
                    const coloredLogs = logs.map(line => this.colorizeLogLine(line)).join('\n');
                    this.consoleElement.innerHTML = coloredLogs;
                    this.consoleElement.scrollTop = this.consoleElement.scrollHeight;
                    return; // 有保存的日志，直接显示，不显示初始消息
                }
            } catch (e) {
                console.warn('Failed to parse persisted log:', e);
            }
        }
        // 如果没有保存的日志，保持HTML中已有的初始消息
        // 不覆盖HTML中的初始内容
    }

    appendLog(message) {
        // 添加消息验证
        if (message === null || message === undefined) {
            console.warn('Attempted to append null or undefined message');
            return;
        }

        let logs = [];
        const saved = localStorage.getItem(this.storageKey);
        if (saved) {
            try {
                logs = JSON.parse(saved);
                if (!Array.isArray(logs)) logs = [];
            } catch (e) {
                logs = [];
            }
        }

        logs.push(message.toString()); // 确保存储为字符串

        if (logs.length > MAX_LOG_LINES) logs = logs.slice(-MAX_LOG_LINES);
        localStorage.setItem(this.storageKey, JSON.stringify(logs));

        const coloredLogs = logs.map(line => this.colorizeLogLine(line)).join('\n');
        this.consoleElement.innerHTML = coloredLogs;
        this.consoleElement.scrollTop = this.consoleElement.scrollHeight;
    }

    clearLog() {
        localStorage.removeItem(this.storageKey);
        // 恢复到初始消息
        const initialMessage = this.appName === 'search'
            ? '<span class="log-info">在左侧选择模块以继续</span>'
            : '<span class="log-info">在左侧选择任务以继续</span>';
        this.consoleElement.innerHTML = initialMessage;
        this.consoleElement.scrollTop = 0;
    }
}

// 工具函数
function formatDateTime(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `[${year}-${month}-${day} ${hours}:${minutes}:${seconds}]`;
}

function safeId(str) {
    return str.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_');
}

function toggleCheckAll(groupName, checked) {
    const checkboxes = document.querySelectorAll(`.checkbox-group[data-group="${groupName}"] input[type="checkbox"]`);
    checkboxes.forEach(cb => {
        cb.checked = checked;
    });
}

// API调用封装
async function callAPI(endpoint, method = 'POST', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (body) options.body = JSON.stringify(body);

    try {
        const res = await fetch(endpoint, options);
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.message || 'Request failed');
        }
        return data;
    } catch (err) {
        console.error('API Error:', err);
        throw err;
    }
}
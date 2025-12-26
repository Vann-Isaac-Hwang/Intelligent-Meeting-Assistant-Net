import dearpygui.dearpygui as dpg
import time
import os

from client_core.api_client import APIClient
from client_core.local_recorder import RealTimeAudioProvider

# ================= 全局配置 =================
SERVER_URL = "http://127.0.0.1:8001"
CONFIG_DIR = os.path.join(os.getcwd(), "config")
os.makedirs(CONFIG_DIR, exist_ok=True)

# ================= 全局单例 =================
api = APIClient(base_url=SERVER_URL)
recorder = RealTimeAudioProvider(resource_path="resource/temp") 

FONTS = {}
GLOBAL_SUMMARY_CACHE = "" 

# 当前用户信息
CURRENT_USER_INFO = {
    "username": None,
    "role": None,
    "uid": None
}

def is_admin():
    """判断当前用户是否为管理员"""
    return CURRENT_USER_INFO.get("role") == "admin"

# ================= 文本清洗工具 (修复问号问题) =================

def clean_emoji(text):
    """
    将文本中可能导致乱码的 Emoji 替换为安全的 ASCII 字符
    """
    if not text: return text
    
    # 定义替换字典 (根据 LLM 习惯和界面常用符号)
    replacements = {
        "✅": "[OK]",
        "❌": "[Err]",
        "⚠️": "[!]",
        "⏳": "...",
        "▶": ">",
        "🗑️": "[Del]",
        "💡": "[Idea]",
        "📝": "[Note]",
        "📅": "[Date]",
        "📍": "[Loc]",
        "👤": "[User]",
        "•": "-",   # 有些字体的 bullet point 也会挂
        "·": "-",
        "—": "-"
    }
    
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

# ================= 公共工具函数 =================

def render_markdown(container_tag, markdown_text):
    global GLOBAL_SUMMARY_CACHE
    if not dpg.does_item_exist(container_tag): return
    
    # 清洗整个文本，防止 Markdown 里的 Emoji 变问号
    markdown_text = clean_emoji(markdown_text)
    
    dpg.delete_item(container_tag, children_only=True)
    GLOBAL_SUMMARY_CACHE = markdown_text 
    
    lines = markdown_text.split('\n')
    with dpg.group(parent=container_tag):
        dpg.add_spacer(height=10)
        for line in lines:
            line = line.strip()
            if not line: 
                dpg.add_spacer(height=8)
                continue
            
            # 简单的 Markdown 解析
            if line.startswith("# "):
                t = dpg.add_text(line[2:], color=(255, 215, 0), wrap=450)
                if "h1" in FONTS: dpg.bind_item_font(t, FONTS["h1"])
                dpg.add_separator()
            elif line.startswith("## "):
                t = dpg.add_text(line[3:], color=(200, 200, 255), wrap=450)
                if "h2" in FONTS: dpg.bind_item_font(t, FONTS["h2"])
            elif line.startswith("- "): 
                dpg.add_text(f"- {line[2:]}", indent=20, wrap=430)
            else: 
                dpg.add_text(line, wrap=450)

def log(msg, is_result=False):
    t = time.strftime("%H:%M:%S")
    
    # 清洗日志内容
    msg = clean_emoji(msg)
    
    if dpg.does_item_exist("LogBox"):
        dpg.add_text(f"[{t}] {msg}", parent="LogBox")
        if dpg.does_item_exist("LogWindow"): 
            dpg.set_y_scroll("LogWindow", 99999)

    if is_result:
        # 如果是摘要/纪要
        if msg.startswith("# ") or "会议纪要" in msg:
            render_markdown("SummaryContainer", msg)
            if dpg.does_item_exist("ResultTabs"):
                dpg.set_value("ResultTabs", "tab_summary")
        
        # 如果是实时转录片段
        elif msg.startswith("[") or msg.startswith("chunk"):
             if dpg.does_item_exist("TranscriptBox"):
                dpg.add_text(msg, parent="TranscriptBox", color=(150, 255, 150), wrap=380)
                if dpg.does_item_exist("TranscriptWindow"): 
                    dpg.set_y_scroll("TranscriptWindow", 99999)
        
        # 其他系统消息
        else:
             if dpg.does_item_exist("TranscriptBox"):
                dpg.add_text(f">>> {msg}", parent="TranscriptBox", color=(255, 255, 0))
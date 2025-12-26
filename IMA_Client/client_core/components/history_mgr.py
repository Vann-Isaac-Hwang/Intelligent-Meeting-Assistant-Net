import dearpygui.dearpygui as dpg
import threading
import os
import webbrowser
from client_core.app_state import api, log, render_markdown

# 状态存储
HISTORY_DATA = []  # 存储列表原始数据
CURRENT_HISTORY_TASK_ID = None

def refresh_history_list():
    """从服务器拉取最新历史记录并刷新列表"""
    global HISTORY_DATA
    log("Refreshing history...")
    data = api.get_history() # 返回 [{task_id, file_name, status, created_at}, ...]
    HISTORY_DATA = data
    
    display_items = []
    for item in data:
        # 格式化显示：[时间] 文件名 (状态)
        time_str = item.get('created_at', 'N/A').split(' ')[0] # 只取日期
        fname = item.get('file_name', 'Unknown')
        status = item.get('status', 'Unknown')
        
        icon = "T" if status == 'completed' else "F" if status == 'failed' else "U"
        display_items.append(f"{icon} [{time_str}] {fname}")
    
    dpg.configure_item("HistoryList", items=display_items)
    log(f"History refreshed. {len(data)} records found.")

def on_history_selected(sender, app_data):
    """当用户点击列表某一项时"""
    global CURRENT_HISTORY_TASK_ID
    if not app_data: return
    
    # app_data 是选中的字符串，我们需要找到对应的 task_id
    # 这里简单通过 index 来找（前提是列表顺序没变）
    try:
        # 获取选中项的索引
        all_items = dpg.get_item_configuration("HistoryList")["items"]
        index = all_items.index(app_data)
        task_info = HISTORY_DATA[index]
        CURRENT_HISTORY_TASK_ID = task_info['task_id']
        
        # 加载详情
        load_task_details(CURRENT_HISTORY_TASK_ID)
    except Exception as e:
        log(f"Error selecting history: {e}")

def load_task_details(task_id):
    """获取详情并显示在右侧"""
    dpg.set_value("hist_loading", "Loading details...")
    
    # 异步获取，防止卡顿
    def _fetch():
        details = api.get_task_status(task_id) # 获取完整详情（含 transcript, markdown）
        if details:
            # 更新 UI 必须在主线程（DPG特性：大部分简单set_value可以跨线程，但复杂的最好注意）
            # 这里简单直接调用
            transcript = details.get('transcript', '(No Transcript)')
            summary = details.get('markdown', '(No Summary)')
            
            # 1. 填充 Transcript
            dpg.set_value("HistTranscriptBox", transcript)
            
            # 2. 渲染 Summary Markdown
            render_markdown("HistSummaryContainer", summary)
            
            # 3. 启用播放按钮
            dpg.configure_item("btn_play_audio", enabled=True)
            dpg.set_value("hist_loading", "")
        else:
            dpg.set_value("hist_loading", "Failed to load details.")

    threading.Thread(target=_fetch, daemon=True).start()

def btn_download_play_click():
    """下载并播放音频"""
    if not CURRENT_HISTORY_TASK_ID: return
    
    def _task():
        dpg.set_value("hist_loading", "Downloading audio...")
        # 下载到临时目录
        temp_dir = "resource/temp_downloads"
        os.makedirs(temp_dir, exist_ok=True)
        save_path = os.path.join(temp_dir, f"{CURRENT_HISTORY_TASK_ID}.wav")
        
        success, msg = api.download_audio(CURRENT_HISTORY_TASK_ID, save_path)
        if success:
            dpg.set_value("hist_loading", "Opening player...")
            # 调用系统默认播放器打开
            try:
                webbrowser.open(os.path.abspath(save_path))
            except Exception as e:
                log(f"Play error: {e}")
            dpg.set_value("hist_loading", "")
        else:
            dpg.set_value("hist_loading", f"Download failed: {msg}")
            
    threading.Thread(target=_task, daemon=True).start()

def init_history_tab():
    with dpg.tab(label=" History "):
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=10)
            dpg.add_button(label="Refresh List", callback=refresh_history_list, width=150)
            dpg.add_text("", tag="hist_loading", color=(255, 200, 0))
            
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            # === 左侧：列表 ===
            with dpg.child_window(width=300):
                dpg.add_listbox(tag="HistoryList", width=-1, num_items=30, callback=on_history_selected)
            
            # === 右侧：详情 ===
            with dpg.child_window(width=-1):
                # 顶部工具栏
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Play / Download Audio", tag="btn_play_audio", enabled=False, callback=btn_download_play_click)
                    # dpg.add_button(label="Export Text") # 未来可加
                
                dpg.add_spacer(height=5)
                
                with dpg.tab_bar():
                    with dpg.tab(label=" Summary (Markdown) "):
                        with dpg.child_window(tag="HistSummaryWindow"):
                            dpg.add_group(tag="HistSummaryContainer")
                            
                    with dpg.tab(label=" Transcript (Full Text) "):
                        with dpg.child_window():
                            dpg.add_input_text(tag="HistTranscriptBox", multiline=True, width=-1, height=-1, readonly=True)
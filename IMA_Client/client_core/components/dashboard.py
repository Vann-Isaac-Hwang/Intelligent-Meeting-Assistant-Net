import dearpygui.dearpygui as dpg
import threading
import time
import datetime
import os
import tkinter as tk
from tkinter import filedialog

from client_core.app_state import api, recorder, log, GLOBAL_SUMMARY_CACHE, render_markdown
from client_core.components.node_editor import get_current_pipeline_config 

# 模块状态
IS_POLLING = False
CURRENT_TASK_ID = None

# ================= 任务轮询逻辑 =================
def start_polling(tid):
    global IS_POLLING, CURRENT_TASK_ID
    IS_POLLING = True
    CURRENT_TASK_ID = tid
    dpg.configure_item("btn_cancel", show=True)
    threading.Thread(target=poll_task_thread, args=(tid,), daemon=True).start()

def poll_task_thread(tid):
    global IS_POLLING
    last_idx = 0
    while IS_POLLING:
        st = api.get_task_status(tid)
        if not st: 
            time.sleep(2)
            continue
            
        if "progress" in st: 
            dpg.set_value("ProgressBar", st["progress"])
            
        logs = st.get("logs", [])
        if len(logs) > last_idx:
            for l in logs[last_idx:]: 
                log(f"[Server] {l}", is_result=True)
            last_idx = len(logs)
            
        if st.get("markdown"): 
            render_markdown("SummaryContainer", st["markdown"])
            dpg.set_value("ResultTabs", "tab_summary")
            
        if st.get("state") in ["completed", "failed", "cancelled"]: 
            log(f"Task {st.get('state').upper()}!")
            IS_POLLING = False
            dpg.configure_item("btn_cancel", show=False)
            break
            
        time.sleep(1)

# ================= 按钮回调 =================
def btn_rec_click(s):
    if "Start" in dpg.get_item_label(s):
        dpg.set_item_label(s, "Stop & Upload")
        dpg.bind_item_theme(s, "theme_red")
        dpg.configure_item("btn_cancel", show=False)
        
        recorder.start(f"meet_{int(time.time())}")
        log("Recording meeting...")
    else:
        dpg.set_item_label(s, "Start Recording")
        dpg.bind_item_theme(s, "theme_green")
        
        recorder.stop()
        log("Uploading meeting audio...")
        if recorder.last_file:
            cfg = get_current_pipeline_config()
            tid = api.create_meeting_task(recorder.last_file, cfg)
            if tid: 
                log(f"Task {tid} started.")
                start_polling(tid)

def btn_cancel_click():
    if CURRENT_TASK_ID and api.cancel_task(CURRENT_TASK_ID): 
        log(">>> Cancelling...")

def btn_load_click():
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
    p = filedialog.askopenfilename()
    root.destroy()
    if p:
        log(f">>> File: {os.path.basename(p)}")
        cfg = get_current_pipeline_config()
        tid = api.create_meeting_task(p, cfg)
        if tid: 
            log(f"Task {tid} started.")
            start_polling(tid)

def btn_export_summary():
    from client_core.app_state import GLOBAL_SUMMARY_CACHE as cache
    if not cache: return log("No summary.")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    f = f"Meeting_Minutes_{ts}.md"
    with open(f, "w", encoding="utf-8") as file: 
        file.write(cache)
    log(f"Exported: {f}")
    os.startfile(os.path.abspath(f))

# [新增] 修改密码弹窗
def btn_change_pwd_modal():
    if dpg.does_item_exist("ChangePwdModal"):
        dpg.show_item("ChangePwdModal")
        return

    def _do_change():
        old = dpg.get_value("cp_old")
        new = dpg.get_value("cp_new")
        if not old or not new: return
        
        success, msg = api.change_own_password(old, new)
        if success:
            log("Password changed successfully.")
            dpg.delete_item("ChangePwdModal")
        else:
            dpg.set_value("cp_msg", f"Error: {msg}")

    with dpg.window(label="Change Password", modal=True, tag="ChangePwdModal", width=300, height=200):
        dpg.add_input_text(label="Old Password", tag="cp_old", password=True)
        dpg.add_input_text(label="New Password", tag="cp_new", password=True)
        dpg.add_spacer(height=10)
        dpg.add_button(label="Update", width=-1, callback=_do_change)
        dpg.add_text("", tag="cp_msg", color=(255, 50, 50))

# ================= 模块入口 =================
def init_dashboard_tab():
    with dpg.tab(label=" Dashboard "):
        dpg.add_spacer(height=15)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=20)
            dpg.add_button(label="Start Recording", tag="btn_rec", width=220, height=60, callback=btn_rec_click)
            dpg.bind_item_theme("btn_rec", "theme_green")
            dpg.add_spacer(width=20)
            dpg.add_button(label="CANCEL TASK", tag="btn_cancel", width=150, height=60, show=False, callback=btn_cancel_click)
            dpg.bind_item_theme("btn_cancel", "theme_red")
            dpg.add_spacer(width=20)
            with dpg.group():
                dpg.add_button(label="Import Audio File", width=180, height=25, callback=btn_load_click)
                dpg.add_spacer(height=5)
                dpg.add_button(label="Export Summary", width=180, height=25, callback=btn_export_summary)
                dpg.add_spacer(height=5)
                # [新增] 修改密码按钮
                dpg.add_button(label="Account Settings", width=180, height=25, callback=btn_change_pwd_modal)
        
        dpg.add_spacer(height=15)
        dpg.add_progress_bar(tag="ProgressBar", width=-20)
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            with dpg.child_window(width=350): 
                dpg.add_group(tag="LogBox")
            with dpg.child_window(width=-1):
                with dpg.tab_bar(tag="ResultTabs"):
                    with dpg.tab(label="Transcript"): 
                        with dpg.child_window(tag="TranscriptWindow"): 
                            dpg.add_group(tag="TranscriptBox")
                    with dpg.tab(label="Summary", tag="tab_summary"): 
                        with dpg.child_window(tag="SummaryWindow"): 
                            dpg.add_group(tag="SummaryContainer")
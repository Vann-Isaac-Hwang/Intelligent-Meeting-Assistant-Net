import dearpygui.dearpygui as dpg
import time
import os
import tkinter as tk
from tkinter import filedialog
from client_core.app_state import api, recorder, log, is_admin # [修改] 导入 is_admin

SELECTED_SPEAKER = None

def refresh_speakers():
    s = api.get_speaker_list()
    items = []
    if s:
        for x in s:
            if isinstance(x, dict):
                items.append(f"{x.get('name', '?')} ({x.get('title', '?')})")
            else:
                items.append(str(x))
    dpg.configure_item("SpeakerList", items=items)

def on_speaker_selected(sender, app_data):
    global SELECTED_SPEAKER
    if not app_data: return
    try:
        if " (" in app_data:
            name_part = app_data.split(" (")[0]
        else:
            name_part = app_data
            
        SELECTED_SPEAKER = name_part
        dpg.set_value("edit_name", name_part)
        dpg.set_value("edit_title", "Unknown") 
        dpg.set_value("SpeakerToolsTabs", "tab_edit_spk")
    except: pass

# ================= 按钮回调 =================

def btn_update_spk():
    # [权限拦截]
    if not is_admin():
        log("❌ Permission Denied: Admin only.")
        return

    if not SELECTED_SPEAKER: return log("No speaker selected.")
    new_name = dpg.get_value("edit_name").strip()
    new_title = dpg.get_value("edit_title").strip()
    if not new_name: return log("Name required.")
    
    success, msg = api.update_speaker(SELECTED_SPEAKER, new_name, new_title)
    if success: log(f"✅ {msg}"); refresh_speakers()
    else: log(f"❌ Error: {msg}")

def btn_delete_spk():
    # [权限拦截]
    if not is_admin():
        log("❌ Permission Denied: Admin only.")
        return

    if not SELECTED_SPEAKER: return log("No speaker selected.")
    success, msg = api.delete_speaker(SELECTED_SPEAKER)
    if success: log(f"🗑️ {msg}"); refresh_speakers(); dpg.set_value("edit_name", "")
    else: log(f"❌ Error: {msg}")

def spk_btn_record_add(s):
    # [权限拦截] (开始前检查)
    if "Start" in dpg.get_item_label(s) and not is_admin():
        log("❌ Permission Denied: Admin only.")
        return

    label = dpg.get_item_label(s)
    if "Start" in label:
        name = dpg.get_value("SpeakerNameInput").strip()
        if not name: log("Enter Name first!"); return
        
        dpg.set_item_label(s, "Stop & Upload")
        dpg.bind_item_theme(s, "theme_red")
        
        recorder.start(f"reg_{int(time.time())}")
        log(">>> Start recording voiceprint...")
        
    else:
        dpg.set_item_label(s, "Start Recording")
        dpg.bind_item_theme(s, "theme_green")
        
        recorder.stop()
        log(">>> Stop recording.")
        
        name = dpg.get_value("SpeakerNameInput").strip()
        title = dpg.get_value("SpeakerTitleInput").strip()
        
        if recorder.last_file:
            log(f"Registering {name}...")
            success, msg = api.register_speaker(name, title, recorder.last_file)
            if success: log("✅ Registered!"); refresh_speakers()
            else: log(f"❌ Error: {msg}")
        else:
            log("❌ No audio recorded.")

def spk_btn_add_file():
    # [权限拦截]
    if not is_admin():
        log("❌ Permission Denied: Admin only.")
        return

    name = dpg.get_value("SpeakerNameInput").strip()
    title = dpg.get_value("SpeakerTitleInput").strip()
    if not name: log("Enter Name first!"); return
    
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
    p = filedialog.askopenfilename()
    root.destroy()
    
    if p:
        log(f"Registering from file: {os.path.basename(p)}")
        success, msg = api.register_speaker(name, title, p)
        if success: log("✅ Registered!"); refresh_speakers()

# ================= 模块入口 =================
def init_speaker_tab():
    with dpg.tab(label=" Speaker Manager "):
         with dpg.group(horizontal=True):
            with dpg.child_window(width=350):
                dpg.add_text("Database Speakers", color=(0, 255, 255))
                dpg.add_separator()
                dpg.add_listbox(tag="SpeakerList", width=-1, num_items=25, callback=on_speaker_selected)
                dpg.add_spacer(height=5)
                dpg.add_button(label="Refresh List", callback=refresh_speakers, width=-1)
            
            with dpg.child_window(width=-1):
                with dpg.tab_bar(tag="SpeakerToolsTabs"):
                    # Tab 1: 编辑/删除 (给里面的按钮加上 Tag 以便显隐控制)
                    with dpg.tab(label="Edit Selected", tag="tab_edit_spk"):
                        dpg.add_spacer(height=10)
                        dpg.add_text("Edit Info", color=(255, 200, 100))
                        dpg.add_input_text(label="Name", tag="edit_name")
                        dpg.add_input_text(label="Title", tag="edit_title")
                        dpg.add_spacer(height=20)
                        with dpg.group(horizontal=True):
                            # [修改] 给按钮加 Tag
                            dpg.add_button(label="Update Info", tag="btn_upd_spk", width=150, height=40, callback=btn_update_spk)
                            dpg.add_spacer(width=20)
                            dpg.add_button(label="DELETE SPEAKER", tag="btn_del_spk", width=150, height=40, callback=btn_delete_spk)
                            dpg.bind_item_theme("btn_del_spk", "theme_btn_del")
                        dpg.add_spacer(height=20)
                        dpg.add_text("Note: Deleting is irreversible.", color=(150,150,150))
                    
                    # Tab 2: 注册新声纹 (给整个 Tab 加 Tag 以便显隐控制)
                    with dpg.tab(label="Register New", tag="tab_new_spk"):
                        dpg.add_spacer(height=10)
                        dpg.add_text("Register Voiceprint (Admin Only)", color=(100, 255, 100))
                        dpg.add_separator()
                        dpg.add_text("1. Metadata:")
                        dpg.add_input_text(label="Name", tag="SpeakerNameInput")
                        dpg.add_input_text(label="Title", tag="SpeakerTitleInput")
                        dpg.add_spacer(height=20)
                        dpg.add_text("2. Audio Source:")
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="Start Recording", width=140, height=50, tag="btn_spk_rec", callback=spk_btn_record_add)
                            dpg.bind_item_theme("btn_spk_rec", "theme_green")
                            dpg.add_spacer(width=20)
                            dpg.add_button(label="Import File", width=140, height=50, callback=spk_btn_add_file)
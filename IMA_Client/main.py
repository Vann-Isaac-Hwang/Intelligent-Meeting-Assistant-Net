import dearpygui.dearpygui as dpg
import time
import os
import sys

# 1. 导入核心工具
try:
    from client_core.ui_utils import FontManager 
    from client_core.app_state import api, log, FONTS, SERVER_URL, CONFIG_DIR, CURRENT_USER_INFO, is_admin
except ImportError as e:
    print(f"[Client] Import Error: {e}")
    time.sleep(5); sys.exit()

# 2. 导入各个 UI 模块
from client_core.components.dashboard import init_dashboard_tab
from client_core.components.speaker_mgr import init_speaker_tab, refresh_speakers
from client_core.components.node_editor import init_node_editor_tab
from client_core.components.history_mgr import init_history_tab, refresh_history_list
# [新增] 导入用户管理
from client_core.components.user_mgr import init_user_mgr_tab, refresh_user_list

def login_modal():
    """登录/注册弹窗"""
    if dpg.does_item_exist("LoginWindow"): 
        dpg.show_item("LoginWindow")
        return

    def perform_login():
        u = dpg.get_value("login_user")
        p = dpg.get_value("login_pass")
        success, data = api.login(u, p)
        if success:
            dpg.delete_item("LoginWindow")
            
            CURRENT_USER_INFO.update(data)
            role = data['role']
            log(f">>> Welcome, {data['username']} ({role})")
            
            # 刷新各个模块的数据
            refresh_speakers()
            refresh_history_list()
            
            # 权限控制 UI
            if role == 'admin':
                dpg.configure_item("btn_del_spk", show=True)
                dpg.configure_item("btn_upd_spk", show=True)
                dpg.configure_item("tab_new_spk", show=True)
                
                # [新增] 显示用户管理并刷新
                dpg.configure_item("tab_user_mgr", show=True)
                refresh_user_list()
            else:
                dpg.configure_item("btn_del_spk", show=False)
                dpg.configure_item("btn_upd_spk", show=False)
                dpg.configure_item("tab_new_spk", show=False)
                
                # [新增] 隐藏用户管理
                dpg.configure_item("tab_user_mgr", show=False)
                
        else:
            dpg.set_value("login_msg", "Login Failed!")

    def perform_register():
        u = dpg.get_value("reg_user")
        p = dpg.get_value("reg_pass")
        code = dpg.get_value("reg_code")
        
        if not u or not p:
            dpg.set_value("reg_msg", "Username & Password required")
            return
            
        success, msg = api.register(u, p, code)
        if success:
            dpg.set_value("reg_msg", "Success! Please Login.")
            dpg.set_value("LoginTabs", "tab_login")
            dpg.set_value("login_user", u)
            dpg.set_value("login_msg", "Account created.")
        else:
            dpg.set_value("reg_msg", f"Error: {msg}")

    with dpg.window(label="System Access", modal=True, tag="LoginWindow", width=320, height=280, no_close=True):
        dpg.add_text(f"Server: {SERVER_URL}", color=(100,255,255))
        dpg.add_spacer(height=5)
        
        with dpg.tab_bar(tag="LoginTabs"):
            with dpg.tab(label=" Login ", tag="tab_login"):
                dpg.add_spacer(height=10)
                dpg.add_input_text(label="User", tag="login_user", default_value="admin")
                dpg.add_input_text(label="Pass", tag="login_pass", password=True, default_value="123456")
                dpg.add_spacer(height=15)
                dpg.add_button(label="LOGIN", callback=perform_login, width=-1, height=30)
                dpg.add_spacer(height=5)
                dpg.add_text("", tag="login_msg", color=(255,100,100))

            with dpg.tab(label=" Register ", tag="tab_register"):
                dpg.add_spacer(height=10)
                dpg.add_input_text(label="User", tag="reg_user")
                dpg.add_input_text(label="Pass", tag="reg_pass", password=True)
                dpg.add_input_text(label="Invite Code", tag="reg_code", hint="Optional (For Admin)")
                dpg.add_spacer(height=15)
                dpg.add_button(label="CREATE ACCOUNT", callback=perform_register, width=-1, height=30)
                dpg.add_spacer(height=5)
                dpg.add_text("", tag="reg_msg", color=(255,100,100))

def build_gui():
    dpg.create_context()
    
    try: 
        FONTS.update(FontManager().setup_fonts())
    except: 
        print("Warning: FontManager setup failed or missing.")
    
    with dpg.theme(tag="theme_red"):
        with dpg.theme_component(dpg.mvButton): 
            dpg.add_theme_color(dpg.mvThemeCol_Button, (200,50,50))
    with dpg.theme(tag="theme_green"):
        with dpg.theme_component(dpg.mvButton): 
            dpg.add_theme_color(dpg.mvThemeCol_Button, (50,150,50))
    with dpg.theme(tag="theme_btn_del"):
        with dpg.theme_component(dpg.mvButton): 
            dpg.add_theme_color(dpg.mvThemeCol_Button, (180, 0, 0))

    with dpg.window(tag="Primary"):
        with dpg.tab_bar():
            init_dashboard_tab()   # 1. 仪表盘
            init_history_tab()     # 2. 历史记录
            init_speaker_tab()     # 3. 说话人管理
            init_user_mgr_tab()    # [新增] 4. 用户管理 (默认隐藏)
            init_node_editor_tab() # 5. 管道配置

    dpg.create_viewport(title="IMA Client v3.3 (User Mgmt)", width=1280, height=800)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary", True)
    
    login_modal()
    
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    print(f"[Client] Connecting to: {SERVER_URL}")
    build_gui()
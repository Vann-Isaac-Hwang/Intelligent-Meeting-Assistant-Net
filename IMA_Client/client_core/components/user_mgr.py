import dearpygui.dearpygui as dpg
from client_core.app_state import api, log

SELECTED_USER = None

def refresh_user_list():
    users = api.get_all_users() # [{username, role, created_at}, ...]
    items = []
    if users:
        for u in users:
            items.append(f"{u['username']} ({u['role']})")
    dpg.configure_item("UserList", items=items)

def on_user_selected(sender, app_data):
    global SELECTED_USER
    if not app_data: return
    # 格式 "admin (admin)"
    SELECTED_USER = app_data.split(" (")[0]
    dpg.set_value("selected_user_txt", f"Selected: {SELECTED_USER}")

def btn_del_user():
    if not SELECTED_USER: return log("Select a user first.")
    if SELECTED_USER == "admin": return log("Cannot delete admin.")
    
    success, msg = api.delete_user(SELECTED_USER)
    if success:
        log(f"User {SELECTED_USER} deleted.")
        refresh_user_list()
    else:
        log(f"Error: {msg}")

def btn_reset_pwd():
    if not SELECTED_USER: return log("Select a user first.")
    new_pw = dpg.get_value("new_pwd_input")
    if not new_pw: return log("Enter new password.")
    
    success, msg = api.admin_reset_password(SELECTED_USER, new_pw)
    if success:
        log(f"Password for {SELECTED_USER} reset.")
        dpg.set_value("new_pwd_input", "")
    else:
        log(f"Error: {msg}")

def init_user_mgr_tab():
    with dpg.tab(label=" User Manager ", tag="tab_user_mgr", show=False): # 默认隐藏
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            # 左侧列表
            with dpg.child_window(width=250):
                dpg.add_text("All Users")
                dpg.add_separator()
                dpg.add_listbox(tag="UserList", width=-1, num_items=20, callback=on_user_selected)
                dpg.add_spacer(height=5)
                dpg.add_button(label="Refresh", width=-1, callback=refresh_user_list)
            
            # 右侧操作
            with dpg.child_window(width=-1):
                dpg.add_text("User Operations", color=(100, 255, 255))
                dpg.add_text("None", tag="selected_user_txt", color=(255, 200, 0))
                dpg.add_separator()
                
                dpg.add_spacer(height=20)
                dpg.add_text("1. Reset Password (Admin Force)")
                dpg.add_input_text(label="New Password", tag="new_pwd_input", password=True)
                dpg.add_button(label="Reset Password", callback=btn_reset_pwd)
                
                dpg.add_spacer(height=30)
                dpg.add_text("2. Danger Zone")
                dpg.add_button(label="DELETE USER", callback=btn_del_user)
                dpg.bind_item_theme(dpg.last_item(), "theme_btn_del")
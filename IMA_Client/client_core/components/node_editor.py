import dearpygui.dearpygui as dpg
import json
import os
import tkinter as tk
from tkinter import filedialog
from client_core.ui_utils import create_node
from client_core.app_state import log, CONFIG_DIR

# ================= 节点 UI 构建器 =================
def build_enhancer_ui(nid): 
    dpg.add_checkbox(label="Enable", default_value=True, tag=f"chk_enhance_{nid}")

def build_vad_ui(nid): 
    dpg.add_slider_int(label="Aggressiveness", default_value=3, min_value=0, max_value=3, width=120, tag=f"vad_agg_{nid}")

def build_spk_ui(nid): 
    dpg.add_drag_float(label="Win(s)", default_value=1.5, width=60, tag=f"win_{nid}")
    dpg.add_drag_float(label="Step(s)", default_value=0.75, width=60, tag=f"step_{nid}")

def build_asr_ui(nid): 
    dpg.add_combo(["tiny","small","base","medium"], default_value="small", width=100, tag=f"model_{nid}")
    dpg.add_checkbox(label="Full Correction", default_value=True, tag=f"chk_ftc_{nid}")
    dpg.add_checkbox(label="Enhanced Audio", default_value=True, tag=f"chk_enhance_audio_{nid}")

def build_llm_ui(nid): 
    dpg.add_checkbox(label="Gen Summary", default_value=True, tag=f"chk_llm_{nid}")
    dpg.add_radio_button(["Local","Online"], default_value="Online", tag=f"back_{nid}")

# ================= 节点工厂定义 =================
NODE_FACTORY = {
    "Audio Source":   {"ins": [], "outs": [("Audio Out","AUDIO",(255,100,100))], "ui": None},
    "Audio Enhancer": {"ins": [("In","AUDIO",(255,100,100))], "outs": [("Out","AUDIO",(255,100,100))], "ui": build_enhancer_ui},
    "VAD Detector":   {"ins": [("In","AUDIO",(255,100,100))], "outs": [("Out","AUDIO",(255,100,100))], "ui": build_vad_ui},
    "Speaker ID":     {"ins": [("In","AUDIO",(255,100,100))], "outs": [("Time","TIMELINE",(255,255,100))], "ui": build_spk_ui},
    "Whisper ASR":    {"ins": [("Audio","AUDIO",(255,100,100)), ("Time","TIMELINE",(255,255,100))], "outs": [("Text","TEXT",(100,200,255))], "ui": build_asr_ui},
    "LLM Summary":    {"ins": [("Text","TEXT",(100,200,255))], "outs": [("Report","TEXT",(100,200,255))], "ui": build_llm_ui},
}

CONNECTED_PORTS = set()

# ================= 连线逻辑 =================
def on_link(sender, app_data):
    dpg.add_node_link(app_data[0], app_data[1], parent=sender)
    CONNECTED_PORTS.add(app_data[1]) 

def on_delink(sender, app_data):
    dpg.delete_item(app_data)

# ================= 辅助函数 =================
def is_input_connected(node_id):
    children = dpg.get_item_children(node_id, 1) or []
    input_attrs = [c for c in children if dpg.get_item_configuration(c).get("attribute_type") == dpg.mvNode_Attr_Input]
    if not input_attrs: return True 
    all_links = dpg.get_item_children("NodeEditor", 0) or []
    for link in all_links:
        conf = dpg.get_item_configuration(link)
        if conf.get("attr_1") in input_attrs or conf.get("attr_2") in input_attrs:
            return True
    return False

def get_attr_by_index(node_id, attr_type, index):
    children = dpg.get_item_children(node_id, 1) or []
    candidates = [c for c in children if dpg.get_item_configuration(c).get('attribute_type') == attr_type]
    if index < len(candidates): return candidates[index]
    return None

def get_attr_index(node_id, attr_id):
    children = dpg.get_item_children(node_id, 1)
    target_conf = dpg.get_item_configuration(attr_id)
    target_type = target_conf.get('attribute_type')
    same_type_attrs = [c for c in children if dpg.get_item_configuration(c).get('attribute_type') == target_type]
    try: return target_type, same_type_attrs.index(attr_id)
    except: return None, 0

# ================= 配置读写逻辑 =================
def get_current_pipeline_config():
    config = {
        "enable_enhancer": False, "enable_vad": False, "enable_spk": False, "enable_asr": False, "enable_llm": False,
        "vad_agg": 3, "spk_win": 1.5, "asr_model": "small", "full_correction": False, "enhanced_audio": False, "llm_backend": "Online"
    }
    try:
        node_ids = dpg.get_item_children("NodeEditor", 1) or []
        for nid in node_ids:
            lbl = dpg.get_item_label(nid)
            # 只有连接了输入的节点才会被启用 (Audio Source 除外)
            if lbl != "Audio Source" and not is_input_connected(nid): continue
            try:
                if lbl == "Audio Enhancer": config['enable_enhancer'] = dpg.get_value(f"chk_enhance_{nid}")
                elif lbl == "VAD Detector": config['enable_vad'] = True; config['vad_agg'] = dpg.get_value(f"vad_agg_{nid}")
                elif lbl == "Speaker ID": config['enable_spk'] = True; config['spk_win'] = dpg.get_value(f"win_{nid}")
                elif lbl == "Whisper ASR": config['enable_asr'] = True; config['asr_model'] = dpg.get_value(f"model_{nid}"); config['full_correction'] = dpg.get_value(f"chk_ftc_{nid}"); config['enhanced_audio'] = dpg.get_value(f"chk_enhance_audio_{nid}")
                elif lbl == "LLM Summary": config['enable_llm'] = dpg.get_value(f"chk_llm_{nid}"); config['llm_backend'] = dpg.get_value(f"back_{nid}")
            except: pass
    except: pass
    return config

def save_pipeline_layout():
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
    f = filedialog.asksaveasfilename(initialdir=CONFIG_DIR, defaultextension=".json", filetypes=[("Pipeline Config", "*.json")])
    root.destroy()
    if not f: return
    
    data = {"nodes": [], "links": []}
    node_ids = dpg.get_item_children("NodeEditor", 1) or []
    node_map = {}
    
    for nid in node_ids:
        lbl = dpg.get_item_label(nid)
        pos = dpg.get_item_pos(nid)
        node_map[nid] = lbl
        params = {}
        try:
            if lbl == "Audio Enhancer": params['chk'] = dpg.get_value(f"chk_enhance_{nid}")
            elif lbl == "VAD Detector": params['agg'] = dpg.get_value(f"vad_agg_{nid}")
            elif lbl == "Speaker ID": params['win'] = dpg.get_value(f"win_{nid}"); params['step'] = dpg.get_value(f"step_{nid}")
            elif lbl == "Whisper ASR": params['model'] = dpg.get_value(f"model_{nid}"); params['ftc'] = dpg.get_value(f"chk_ftc_{nid}"); params['enh'] = dpg.get_value(f"chk_enhance_audio_{nid}")
            elif lbl == "LLM Summary": params['chk'] = dpg.get_value(f"chk_llm_{nid}"); params['back'] = dpg.get_value(f"back_{nid}")
        except: pass
        data["nodes"].append({"label": lbl, "pos": pos, "params": params})
        
    links = dpg.get_item_children("NodeEditor", 0) or []
    for link in links:
        c = dpg.get_item_configuration(link)
        a1, a2 = c['attr_1'], c['attr_2']
        n1, n2 = dpg.get_item_parent(a1), dpg.get_item_parent(a2)
        t1, idx1 = get_attr_index(n1, a1)
        t2, idx2 = get_attr_index(n2, a2)
        if t1 == dpg.mvNode_Attr_Output:
            data["links"].append({"src": node_map[n1], "src_idx": idx1, "dst": node_map[n2], "dst_idx": idx2})
        else:
            data["links"].append({"src": node_map[n2], "src_idx": idx2, "dst": node_map[n1], "dst_idx": idx1})
            
    with open(f, "w") as file: json.dump(data, file, indent=2)
    log(f"Config saved: {os.path.basename(f)}")

def load_pipeline_layout(filepath=None):
    if not filepath:
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
        filepath = filedialog.askopenfilename(initialdir=CONFIG_DIR, filetypes=[("Pipeline Config", "*.json")])
        root.destroy()
    if not filepath: return

    try:
        with open(filepath, "r") as file: data = json.load(file)
        dpg.delete_item("NodeEditor", children_only=True)
        label_to_id = {}
        
        for n in data["nodes"]:
            lbl = n["label"]
            spec = NODE_FACTORY.get(lbl)
            if not spec: continue
            nid = create_node(lbl, n["pos"], spec["ins"], spec["outs"], spec["ui"])
            label_to_id[lbl] = nid
            p = n.get("params", {})
            try:
                if lbl == "Audio Enhancer": dpg.set_value(f"chk_enhance_{nid}", p.get('chk', True))
                elif lbl == "VAD Detector": dpg.set_value(f"vad_agg_{nid}", p.get('agg', 3))
                elif lbl == "Speaker ID": dpg.set_value(f"win_{nid}", p.get('win', 1.5)); dpg.set_value(f"step_{nid}", p.get('step', 0.75))
                elif lbl == "Whisper ASR": dpg.set_value(f"model_{nid}", p.get('model', 'small')); dpg.set_value(f"chk_ftc_{nid}", p.get('ftc', True)); dpg.set_value(f"chk_enhance_audio_{nid}", p.get('enh', True))
                elif lbl == "LLM Summary": dpg.set_value(f"chk_llm_{nid}", p.get('chk', True)); dpg.set_value(f"back_{nid}", p.get('back', 'Online'))
            except: pass
            
        for l in data["links"]:
            src_nid = label_to_id.get(l["src"])
            dst_nid = label_to_id.get(l["dst"])
            if src_nid and dst_nid:
                attr_out = get_attr_by_index(src_nid, dpg.mvNode_Attr_Output, l["src_idx"])
                attr_in = get_attr_by_index(dst_nid, dpg.mvNode_Attr_Input, l["dst_idx"])
                if attr_out and attr_in: dpg.add_node_link(attr_out, attr_in, parent="NodeEditor")
        log(f"Loaded config: {os.path.basename(filepath)}")
    except Exception as e: log(f"Load failed: {e}")

def load_default_nodes():
    default_json = os.path.join(CONFIG_DIR, "default_pl.json")
    if os.path.exists(default_json):
        load_pipeline_layout(default_json)
    else:
        # 硬编码默认布局
        dpg.delete_item("NodeEditor", children_only=True)
        y = 100
        n_src = create_node("Audio Source", [50, y], NODE_FACTORY["Audio Source"]["ins"], NODE_FACTORY["Audio Source"]["outs"], None)
        n_enh = create_node("Audio Enhancer", [250, y], NODE_FACTORY["Audio Enhancer"]["ins"], NODE_FACTORY["Audio Enhancer"]["outs"], build_enhancer_ui)
        n_vad = create_node("VAD Detector", [450, y], NODE_FACTORY["VAD Detector"]["ins"], NODE_FACTORY["VAD Detector"]["outs"], build_vad_ui)
        n_spk = create_node("Speaker ID", [650, y-50], NODE_FACTORY["Speaker ID"]["ins"], NODE_FACTORY["Speaker ID"]["outs"], build_spk_ui)
        n_asr = create_node("Whisper ASR", [900, y], NODE_FACTORY["Whisper ASR"]["ins"], NODE_FACTORY["Whisper ASR"]["outs"], build_asr_ui)
        n_llm = create_node("LLM Summary", [1150, y], NODE_FACTORY["LLM Summary"]["ins"], NODE_FACTORY["LLM Summary"]["outs"], build_llm_ui)
        
        def get_attr(nid, is_out=False, idx=0):
            attrs = dpg.get_item_children(nid, 1)
            target_type = dpg.mvNode_Attr_Output if is_out else dpg.mvNode_Attr_Input
            candidates = [a for a in attrs if dpg.get_item_configuration(a)['attribute_type'] == target_type]
            if idx < len(candidates): return candidates[idx]
            return None
            
        dpg.add_node_link(get_attr(n_src, True, 0), get_attr(n_enh, False, 0), parent="NodeEditor")
        dpg.add_node_link(get_attr(n_enh, True, 0), get_attr(n_vad, False, 0), parent="NodeEditor")
        dpg.add_node_link(get_attr(n_vad, True, 0), get_attr(n_spk, False, 0), parent="NodeEditor")
        dpg.add_node_link(get_attr(n_enh, True, 0), get_attr(n_asr, False, 0), parent="NodeEditor")
        dpg.add_node_link(get_attr(n_spk, True, 0), get_attr(n_asr, False, 1), parent="NodeEditor")
        dpg.add_node_link(get_attr(n_asr, True, 0), get_attr(n_llm, False, 0), parent="NodeEditor")

# ================= 模块入口 =================
def init_node_editor_tab():
    with dpg.tab(label=" Pipeline Config "):
        with dpg.group(horizontal=True):
            dpg.add_button(label="Reset Default", callback=lambda: load_default_nodes())
            dpg.add_spacer(width=20)
            dpg.add_button(label="Save Config", callback=save_pipeline_layout)
            dpg.add_button(label="Load Config", callback=lambda: load_pipeline_layout())
        dpg.add_separator()
        with dpg.node_editor(tag="NodeEditor", callback=on_link, delink_callback=on_delink):
            load_default_nodes()
import os
import sys
import json
import traceback
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# 导入业务组件
from utilities.diarization.engine import SpeakerEngine
from core.processors import EnhancerProcessor, VADProcessor, SpeakerIDProcessor, ASRProcessor, LLMProcessor
from app.task_manager import TaskManager

# 导入鉴权组件
from app.auth import (
    GLOBAL_USER_DB, 
    verify_password, 
    create_access_token, 
    get_current_user, 
    require_admin, 
    User
)

app = FastAPI(title="IMA Server (User Management)")

# --- 1. 目录配置 ---
os.makedirs("resource", exist_ok=True)
UPLOAD_DIR = os.path.join("resource", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 挂载静态文件
app.mount("/resource", StaticFiles(directory="resource"), name="resource")

# --- 2. 全局单例模型 ---
print(">>> [Server] Initializing AI Engines...")
GLOBAL_SPEAKER_ENGINE = SpeakerEngine()
print(">>> [Server] AI Engines Ready.")

# --- 3. 请求模型定义 ---
class AuthRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: str = None 

class UpdateSpeakerRequest(BaseModel):
    current_name: str
    new_name: str
    new_title: str

# [新增] 密码修改请求模型
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class AdminResetPasswordRequest(BaseModel):
    new_password: str

# ================= 认证接口 (Authentication) =================

@app.post("/auth/register")
async def register(req: RegisterRequest):
    """用户注册"""
    role = "user"
    if req.invite_code == "IMA_ADMIN_2025": # 管理员邀请码
        role = "admin"
        
    success, msg = GLOBAL_USER_DB.create_user(req.username, req.password, role)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    
    return {"status": "success", "msg": f"User {req.username} created as {role}"}

@app.post("/auth/login")
async def login(req: AuthRequest):
    """用户登录"""
    user = GLOBAL_USER_DB.get_user(req.username)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    # 生成 Token (包含 uid)
    access_token = create_access_token(data={
        "sub": user.username, 
        "role": user.role,
        "uid": user.id 
    })
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "role": user.role, 
        "username": user.username
    }

# [新增] 用户修改自己的密码
@app.post("/auth/password")
async def change_own_password_endpoint(
    req: ChangePasswordRequest, 
    user: User = Depends(get_current_user)
):
    # 1. 验证旧密码
    db_user = GLOBAL_USER_DB.get_user(user.username)
    if not db_user or not verify_password(req.old_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    # 2. 更新新密码
    success, msg = GLOBAL_USER_DB.update_password(user.username, req.new_password)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update password")
    
    return {"status": "success", "msg": "Password updated successfully."}

# ================= 用户管理接口 (Admin Only) =================

@app.get("/users")
async def get_all_users_endpoint(user: User = Depends(require_admin)):
    """获取所有用户列表"""
    return GLOBAL_USER_DB.get_all_users()

@app.delete("/users/{target_username}")
async def delete_user_endpoint(target_username: str, user: User = Depends(require_admin)):
    """删除指定用户"""
    success, msg = GLOBAL_USER_DB.delete_user(target_username)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "msg": msg}

@app.post("/users/{target_username}/reset_password")
async def admin_reset_password_endpoint(
    target_username: str, 
    req: AdminResetPasswordRequest, 
    user: User = Depends(require_admin)
):
    """管理员强制重置用户密码"""
    success, msg = GLOBAL_USER_DB.update_password(target_username, req.new_password)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "msg": f"Password for {target_username} reset successfully."}

# ================= 说话人管理 (仅管理员可写) =================

@app.get("/speakers")
async def get_speakers(user: User = Depends(get_current_user)):
    """获取列表 (登录用户可用)"""
    try:
        raw_data = GLOBAL_SPEAKER_ENGINE.db.get_all_speakers()
        speakers = [
            {"name": row[0], "title": row[1] if row[1] else "Unknown"} 
            for row in raw_data
        ]
        return speakers
    except Exception as e:
        print(f"Error fetching speakers: {e}")
        return []

@app.post("/speakers/register")
async def register_speaker_endpoint(
    name: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_admin)
):
    """注册声纹 (仅管理员)"""
    temp_path = os.path.join(UPLOAD_DIR, f"temp_reg_{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    try:
        success, msg = GLOBAL_SPEAKER_ENGINE.db.add_speaker(name, title, temp_path)
        if success:
            return {"status": "success", "msg": msg}
        else:
            return JSONResponse(status_code=400, content={"detail": msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass

@app.put("/speakers/update")
async def update_speaker_endpoint(
    req: UpdateSpeakerRequest, 
    user: User = Depends(require_admin)
):
    success, msg = GLOBAL_SPEAKER_ENGINE.db.update_speaker_info(
        current_name=req.current_name, 
        new_name=req.new_name, 
        new_title=req.new_title
    )
    if success: return {"status": "success", "msg": msg}
    raise HTTPException(status_code=400, detail=msg)

@app.delete("/speakers/{name}")
async def delete_speaker_endpoint(
    name: str, 
    user: User = Depends(require_admin)
):
    try:
        GLOBAL_SPEAKER_ENGINE.db.delete_speaker(name)
        return {"status": "success", "msg": f"Deleted {name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================= 会议任务流水线 =================

def run_pipeline_background(task_id: str, audio_path: str, config: dict):
    # 1. 初始化内存状态
    TaskManager.init_mem_task(task_id)
    
    print(f"[{task_id}] 📥 Config: {json.dumps(config, indent=2)}")
    TaskManager.mem_update_log(task_id, ">>> Pipeline Started")
    
    def log_callback(msg, is_result=False):
        print(f"[{task_id}] {msg}") 
        TaskManager.mem_update_log(task_id, msg)

    context = {'audio_path': audio_path}
    
    try:
        # 1. Enhancer
        if config.get("enable_enhancer", False):
            log_callback("[Pipeline] Running Enhancer...")
            ctx = EnhancerProcessor().process(context, {"enable": True}, log_callback)
        else:
            log_callback("[Pipeline] Skipped Enhancer.")
        TaskManager.mem_update_progress(task_id, 0.2)
        
        # 2. VAD
        if config.get("enable_vad", False):
            log_callback("[Pipeline] Running VAD...")
            ctx = VADProcessor().process(context, {"aggressiveness": config.get("vad_agg", 3)}, log_callback)
        else:
            log_callback("[Pipeline] Skipped VAD.")
        TaskManager.mem_update_progress(task_id, 0.4)
        
        # 3. Speaker ID
        if config.get("enable_spk", False):
            log_callback("[Pipeline] Running Speaker ID...")
            ctx = SpeakerIDProcessor().process(context, {"window": config.get("spk_win", 1.5), "step": 0.75}, log_callback)
        else:
            log_callback("[Pipeline] Skipped Speaker ID.")
            if 'timeline' not in context: context['timeline'] = []
        TaskManager.mem_update_progress(task_id, 0.6)
        
        # 4. ASR
        if config.get("enable_asr", False):
            log_callback("[Pipeline] Running Whisper ASR...")
            asr_cfg = {
                "model": config.get("asr_model", "small"),
                "full_text_correction": config.get("full_correction", True),
                "enhanced_audio": config.get("enhanced_audio", True)
            }
            resource_dir = os.path.join(BASE_DIR, "resource")
            ctx = ASRProcessor(resource_dir).process(context, asr_cfg, log_callback)
        else:
            log_callback("[Pipeline] Skipped ASR.")
        TaskManager.mem_update_progress(task_id, 0.8)
        
        # 5. LLM
        if config.get("enable_llm", False):
            if context.get('log_path'):
                log_callback("[Pipeline] Running LLM Summary...")
                ctx = LLMProcessor().process(context, {"enable": True, "backend": config.get("llm_backend", "Online")}, log_callback)
            else:
                log_callback("[Pipeline] Skipped LLM (No Transcript).")
        
        # === 任务完成，写入数据库持久化 ===
        transcript = context.get('transcript', "")
        
        # 如果内存中没有，尝试从 Log 文件读取完整转录
        if not transcript and context.get('log_path') and os.path.exists(context['log_path']):
             try:
                 with open(context['log_path'], 'r', encoding='utf-8') as f:
                     transcript = f.read()
             except: pass
        
        # [修复] 优先从 context['summary'] 获取 LLM 生成的摘要
        summary_text = context.get('summary', "Summary not generated.")
        
        TaskManager.update_status(task_id, "completed", transcript, summary_text)
        
    except Exception as e:
        traceback.print_exc()
        TaskManager.update_status(task_id, "failed")
        TaskManager.mem_update_log(task_id, f"Error: {str(e)}")
        
    finally:
        # === 清理逻辑：保留原始音频，只删中间文件 ===
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.abspath(file_path) == os.path.abspath(audio_path):
                    continue
                if task_id in filename:
                    try: os.remove(file_path)
                    except: pass
        
        TaskManager.mem_cleanup(task_id)

@app.post("/tasks/create")
async def create_task(
    config: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    print(f"User {user.username} (ID: {user.id}) creating task...")
    safe_filename = f"task_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    task_id = TaskManager.create_task(user.id, file.filename, file_path)
    
    try: pipeline_config = json.loads(config)
    except: pipeline_config = {}
        
    background_tasks.add_task(run_pipeline_background, task_id, file_path, pipeline_config)
    return {"task_id": task_id}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str, user: User = Depends(get_current_user)):
    status = TaskManager.mem_get_status(task_id)
    if not status: 
        raise HTTPException(status_code=404, detail="Task not found")
    return status

@app.post("/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str, user: User = Depends(get_current_user)):
    return {"status": "ok"}

@app.get("/history")
async def get_history(user: User = Depends(get_current_user)):
    return TaskManager.get_user_history(user.id)

@app.get("/tasks/{task_id}/audio")
async def get_task_audio(task_id: str, user: User = Depends(get_current_user)):
    task = TaskManager.get_task(task_id)
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    if task['user_id'] != user.id and user.role != 'admin':
        raise HTTPException(status_code=403, detail="Permission denied")
    if not os.path.exists(task['audio_path']):
        raise HTTPException(status_code=404, detail="Audio file lost")
    return FileResponse(task['audio_path'], media_type="audio/wav", filename=task['file_name'])
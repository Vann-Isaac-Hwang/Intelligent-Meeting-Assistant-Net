import sqlite3
import uuid
import datetime
import os
import json

# 数据库路径
DB_PATH = "resource/tasks.db"

class TaskManager:
    @staticmethod
    def _init_db():
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # 创建任务表
        c.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                user_id INTEGER,
                file_name TEXT,
                audio_path TEXT,
                status TEXT,
                created_at TEXT,
                transcript TEXT,
                summary TEXT,
                logs TEXT
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def create_task(user_id, file_name, audio_path):
        """创建新任务入库"""
        TaskManager._init_db()
        task_id = str(uuid.uuid4())
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO tasks (task_id, user_id, file_name, audio_path, status, created_at, logs) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, user_id, file_name, audio_path, "processing", created_at, "[]")
        )
        conn.commit()
        conn.close()
        return task_id

    @staticmethod
    def update_log(task_id, message, is_result=False):
        """追加日志（为了性能，日志可以只存内存或定期刷入，这里简化为实时更新）"""
        # 注意：频繁写库可能会慢，但在低并发场景下 SQLite 足够快
        # 这里为了简化，我们暂时只在内存里打印，或者仅在关键状态变更时写库
        # 为了前端轮询能看到实时进度，我们需要一种机制。
        # 方案：对于正在运行的任务，使用内存缓存；任务结束后写入 DB。
        pass # 实际日志逻辑我们在 main.py 的回调里处理，或者这里读写 DB

    @staticmethod
    def update_status(task_id, status, transcript=None, summary=None):
        """更新任务状态和结果"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if transcript and summary:
            c.execute("UPDATE tasks SET status=?, transcript=?, summary=? WHERE task_id=?", 
                     (status, transcript, summary, task_id))
        else:
            c.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, task_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_task(task_id):
        """获取单个任务详情"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "task_id": row[0],
                "user_id": row[1],
                "file_name": row[2],
                "audio_path": row[3], # 原始音频路径
                "status": row[4],
                "created_at": row[5],
                "transcript": row[6],
                "summary": row[7]
            }
        return None

    @staticmethod
    def get_user_history(user_id):
        """获取某用户的所有历史任务"""
        TaskManager._init_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # 按时间倒序
        c.execute("SELECT task_id, file_name, status, created_at FROM tasks WHERE user_id=? ORDER BY created_at DESC", (user_id,))
        rows = c.fetchall()
        conn.close()
        
        history = []
        for r in rows:
            history.append({
                "task_id": r[0],
                "file_name": r[1],
                "status": r[2],
                "created_at": r[3]
            })
        return history

    # --- 内存缓存用于实时轮询 (Progress Polling) ---
    # 由于前端 dashboard 需要轮询 logs 和 progress，直接查库太慢且不方便存进度条 float
    # 我们维护一个简单的内存字典，仅用于“正在进行中”的任务
    _active_tasks = {} 

    @staticmethod
    def init_mem_task(task_id):
        TaskManager._active_tasks[task_id] = {"progress": 0.0, "logs": []}

    @staticmethod
    def mem_update_log(task_id, msg):
        if task_id in TaskManager._active_tasks:
            TaskManager._active_tasks[task_id]["logs"].append(msg)

    @staticmethod
    def mem_update_progress(task_id, p):
        if task_id in TaskManager._active_tasks:
            TaskManager._active_tasks[task_id]["progress"] = p

    @staticmethod
    def mem_get_status(task_id):
        # 优先查内存（正在运行），如果内存没有，查 DB（已完成/历史）
        if task_id in TaskManager._active_tasks:
            return {
                "state": "processing",
                "progress": TaskManager._active_tasks[task_id]["progress"],
                "logs": TaskManager._active_tasks[task_id]["logs"]
            }
        
        # 查 DB
        task = TaskManager.get_task(task_id)
        if task:
            return {
                "state": task["status"],
                "progress": 1.0 if task["status"]=="completed" else 0.0,
                "transcript": task["transcript"],
                "markdown": task["summary"]
            }
        return None

    @staticmethod
    def mem_cleanup(task_id):
        """任务完成后清理内存缓存"""
        if task_id in TaskManager._active_tasks:
            del TaskManager._active_tasks[task_id]
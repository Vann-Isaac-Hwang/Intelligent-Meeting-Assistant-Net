import sqlite3
import datetime
import os
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel

# === 配置 ===
SECRET_KEY = "CHANGE_THIS_TO_A_SUPER_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

# === 密码哈希工具 ===
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
security = HTTPBearer()

# === 数据模型 ===
class User(BaseModel):
    id: Optional[int] = None
    username: str
    role: str

class UserInDB(User):
    password_hash: str

# === 用户数据库管理 ===
class UserDB:
    def __init__(self, db_path="resource/users.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TEXT
            )
        ''')
        
        cursor.execute("SELECT id FROM users WHERE username='admin'")
        if not cursor.fetchone():
            print("[UserDB] Creating default admin account...")
            hashed = pwd_context.hash("123456")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                ("admin", hashed, "admin", datetime.datetime.now().isoformat())
            )
        conn.commit()
        conn.close()

    def get_user(self, username: str) -> Optional[UserInDB]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username=?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return UserInDB(id=row[0], username=row[1], password_hash=row[2], role=row[3])
        return None

    def create_user(self, username, password, role="user"):
        if self.get_user(username):
            return False, "Username already exists"
        
        hashed = pwd_context.hash(password)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, hashed, role, datetime.datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            return True, "User created successfully"
        except Exception as e:
            return False, str(e)

    # --- [新增] 用户管理功能 ---
    
    def get_all_users(self):
        """获取所有用户列表 (仅返回安全字段)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT username, role, created_at FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [{"username": r[0], "role": r[1], "created_at": r[2]} for r in rows]

    def delete_user(self, username):
        """删除用户"""
        if username == "admin":
            return False, "Cannot delete super admin."
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username=?", (username,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted: return True, f"User {username} deleted."
        return False, "User not found."

    def update_password(self, username, new_password):
        """更新密码 (直接覆盖，用于管理员重置或用户修改)"""
        hashed = pwd_context.hash(new_password)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash=? WHERE username=?", (hashed, username))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if updated: return True, "Password updated."
        return False, "User not found."

# 初始化全局数据库实例
GLOBAL_USER_DB = UserDB()

# ... (Auth 辅助函数保持不变) ...
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: int = payload.get("uid")
        if username is None or role is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return User(id=user_id, username=username, role=role)
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def require_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
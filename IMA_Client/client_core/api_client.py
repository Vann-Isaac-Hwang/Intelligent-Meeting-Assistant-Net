import requests
import os
import json
import urllib.parse
from requests.exceptions import RequestException

class APIClient:
    def __init__(self, base_url="http://127.0.0.1:8001"):
        self.base_url = base_url
        self.token = None
        self.headers = {}

    def register(self, username, password, invite_code=""):
        try:
            payload = {"username": username, "password": password, "invite_code": invite_code}
            resp = requests.post(f"{self.base_url}/auth/register", json=payload)
            if resp.status_code == 200:
                return True, "Registration successful"
            return False, resp.json().get("detail", "Registration failed")
        except Exception as e:
            return False, str(e)

    def login(self, username, password):
        try:
            resp = requests.post(f"{self.base_url}/auth/login", json={"username": username, "password": password})
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                return True, {
                    "role": data.get("role", "user"),
                    "username": data.get("username", username),
                    "uid": data.get("uid", None)
                }
            return False, None
        except Exception as e:
            print(f"Login Error: {e}")
            return False, None

    # --- Speaker Methods ---
    def get_speaker_list(self):
        if not self.token: return []
        try:
            resp = requests.get(f"{self.base_url}/speakers", headers=self.headers)
            if resp.status_code == 200: return resp.json()
        except: pass
        return []

    def register_speaker(self, name, title, file_path):
        if not os.path.exists(file_path): return False, "File not found"
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {'name': name, 'title': title}
                resp = requests.post(f"{self.base_url}/speakers/register", headers=self.headers, data=data, files=files)
                if resp.status_code == 200: return True, "Success"
                return False, resp.json().get("detail", "Error")
        except Exception as e: return False, str(e)

    def update_speaker(self, current_name, new_name, new_title):
        payload = {"current_name": current_name, "new_name": new_name, "new_title": new_title}
        try:
            resp = requests.put(f"{self.base_url}/speakers/update", headers=self.headers, json=payload)
            return resp.status_code == 200, resp.json().get("msg", str(resp.text))
        except Exception as e: return False, str(e)

    def delete_speaker(self, name):
        try:
            safe_name = urllib.parse.quote(name)
            resp = requests.delete(f"{self.base_url}/speakers/{safe_name}", headers=self.headers)
            return resp.status_code == 200, resp.json().get("msg", "Error")
        except Exception as e: return False, str(e)

    # --- Task Methods ---
    def create_meeting_task(self, audio_path, pipeline_config):
        try:
            with open(audio_path, 'rb') as f:
                files = {'file': f}
                data = {'config': json.dumps(pipeline_config)}
                resp = requests.post(f"{self.base_url}/tasks/create", headers=self.headers, data=data, files=files)
                if resp.status_code == 200: return resp.json().get("task_id")
        except: pass
        return None

    def get_task_status(self, task_id):
        try:
            resp = requests.get(f"{self.base_url}/tasks/{task_id}", headers=self.headers)
            if resp.status_code == 200: return resp.json() 
        except: pass
        return None

    def cancel_task(self, task_id):
        try:
            resp = requests.post(f"{self.base_url}/tasks/{task_id}/cancel", headers=self.headers)
            return resp.status_code == 200
        except: return False

    # --- History & Audio Methods ---
    def get_history(self):
        if not self.token: return []
        try:
            resp = requests.get(f"{self.base_url}/history", headers=self.headers)
            if resp.status_code == 200: return resp.json()
        except: pass
        return []

    def download_audio(self, task_id, save_path):
        try:
            with requests.get(f"{self.base_url}/tasks/{task_id}/audio", headers=self.headers, stream=True) as r:
                r.raise_for_status()
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True, save_path
        except Exception as e:
            return False, str(e)

    # --- [新增] User Management Methods ---
    def get_all_users(self):
        try:
            resp = requests.get(f"{self.base_url}/users", headers=self.headers)
            if resp.status_code == 200: return resp.json()
        except: pass
        return []

    def delete_user(self, username):
        try:
            resp = requests.delete(f"{self.base_url}/users/{username}", headers=self.headers)
            if resp.status_code == 200: return True, "Deleted"
            return False, resp.json().get("detail", "Failed")
        except Exception as e: return False, str(e)

    def admin_reset_password(self, username, new_password):
        try:
            resp = requests.post(f"{self.base_url}/users/{username}/reset_password", 
                                 headers=self.headers, json={"new_password": new_password})
            if resp.status_code == 200: return True, "Reset Success"
            return False, resp.json().get("detail", "Failed")
        except Exception as e: return False, str(e)

    def change_own_password(self, old_password, new_password):
        try:
            resp = requests.post(f"{self.base_url}/auth/password", 
                                 headers=self.headers, 
                                 json={"old_password": old_password, "new_password": new_password})
            if resp.status_code == 200: return True, "Success"
            return False, resp.json().get("detail", "Failed")
        except Exception as e: return False, str(e)
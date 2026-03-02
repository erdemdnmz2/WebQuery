"""
Session Cache Manager
Kullanıcı session'larını ve şifrelerini bellekte güvenli bir şekilde saklar
"""
from typing import Dict
from cryptography.fernet import Fernet
from datetime import datetime
import os
import redis

import json

class SessionCache:
    def __init__(self, fernet: Fernet | None = None):
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_db = int(os.getenv("REDIS_DB", 0))

        self.client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        self.fernet_instance = fernet

    def add_to_cache(self, password: str, user_id: int):
        if not self.fernet_instance:
            raise RuntimeError("Fernet instance is not initialized")
        
        # Redis sadece string tutabildiği için dictionary'i JSON formatına çeviriyoruz.
        # Fernet şifresi bytes döner, json için string'e çevirmeliyiz (.decode('utf-8'))
        # Datetime objesini de iso string formatına çeviriyoruz (.isoformat())
        sub = {
            "user_password": self.fernet_instance.encrypt(password.encode()).decode('utf-8'),
            "addition_time": datetime.now().isoformat()
        }
        self.client.set(user_id, json.dumps(sub))

    def get_password(self, user_id: int) -> str:
        if not self.fernet_instance:
            raise RuntimeError("Fernet instance is not initialized")
        
        info_str = self.client.get(user_id)
        if not info_str:
            raise KeyError(f"Kullanıcı ({user_id}) cache üzerinde bulunamadı.")
            
        info = json.loads(info_str)
        # JSON'dan gelen string formatındaki şifreli hali tekrar bytes'a çeviriyoruz (.encode('utf-8'))
        encoded_pw = info["user_password"].encode('utf-8')
        password = self.fernet_instance.decrypt(encoded_pw).decode()
        return password

    def remove(self, user_id: int):
        self.client.delete(user_id)

    def is_valid(self, user_id: int, timeout_minutes: int) -> bool:
        info_str = self.client.get(user_id)
        if not info_str:
            return False
            
        info = json.loads(info_str)
        from datetime import datetime, timedelta
        timeout = timedelta(minutes=timeout_minutes)
        addition_time = datetime.fromisoformat(info["addition_time"])
        
        if datetime.now() - addition_time > timeout:
            self.remove(user_id)
            return False
        return True
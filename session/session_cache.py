from typing import Dict
from cryptography.fernet import Fernet
from datetime import datetime

class SessionCache:
    def __init__(self, fernet: Fernet | None = None):
        self.session_cache: Dict[int, Dict] = {}
        self.fernet_instance = fernet
    
    def add_to_cache(self, password: str, user_id: int):
        if not self.fernet_instance:
            raise RuntimeError("Fernet instance is not initialized")
        sub = {
            "user_password": self.fernet_instance.encrypt(password.encode()),
            "addition_time": datetime.now()
        }
        self.session_cache[user_id] = sub

    def get_password(self, user_id: int) -> str:
        if not self.fernet_instance:
            raise RuntimeError("Fernet instance is not initialized")
        encoded_pw = self.session_cache[user_id]["user_password"]
        password = self.fernet_instance.decrypt(encoded_pw).decode()
        return password
    
    def remove(self, user_id: int):
        self.session_cache.pop(user_id, None)

    def is_valid(self, user_id: int, timeout_minutes: int) -> bool:
        info = self.session_cache.get(user_id)
        if not info:
            return False
        from datetime import datetime, timedelta
        timeout = timedelta(minutes=timeout_minutes)
        if datetime.now() - info["addition_time"] > timeout:
            self.remove(user_id)
            return False
        return True
"""
Session Cache Manager
Kullanıcı session'larını ve şifrelerini bellekte güvenli bir şekilde saklar
"""
from typing import Dict
from cryptography.fernet import Fernet
from datetime import datetime

class SessionCache:
    """
    Kullanıcı session yönetimi ve şifre cache'i
    
    Kullanıcı şifrelerini Fernet (symmetric encryption) ile şifreli olarak 
    bellekte saklar ve session timeout kontrolü yapar.
    
    Attributes:
        session_cache: {user_id: {"user_password": encrypted_bytes, "addition_time": datetime}}
        fernet_instance: Şifreleme/deşifreleme için Fernet instance
    """
    
    def __init__(self, fernet: Fernet | None = None):
        """
        SessionCache'i başlatır
        
        Args:
            fernet: Şifreleme için Fernet instance (opsiyonel, sonradan set edilebilir)
        """
        self.session_cache: Dict[int, Dict] = {}
        self.fernet_instance = fernet
    
    def add_to_cache(self, password: str, user_id: int):
        """
        Kullanıcı şifresini şifreleyerek cache'e ekler
        
        Args:
            password: Kullanıcının düz metin şifresi
            user_id: Kullanıcı ID'si
        
        Raises:
            RuntimeError: Fernet instance başlatılmamışsa
        
        Note:
            Şifre Fernet ile symmetric encryption kullanılarak şifrelenir
        """
        if not self.fernet_instance:
            raise RuntimeError("Fernet instance is not initialized")
        sub = {
            "user_password": self.fernet_instance.encrypt(password.encode()),
            "addition_time": datetime.now()
        }
        self.session_cache[user_id] = sub

    def get_password(self, user_id: int) -> str:
        """
        Kullanıcının şifresini deşifreleyerek döndürür
        
        Args:
            user_id: Kullanıcı ID'si
        
        Returns:
            str: Deşifrelenmiş düz metin şifre
        
        Raises:
            RuntimeError: Fernet instance başlatılmamışsa
            KeyError: Kullanıcı cache'te bulunamazsa
        """
        if not self.fernet_instance:
            raise RuntimeError("Fernet instance is not initialized")
        encoded_pw = self.session_cache[user_id]["user_password"]
        password = self.fernet_instance.decrypt(encoded_pw).decode()
        return password
    
    def remove(self, user_id: int):
        """
        Kullanıcıyı session cache'den çıkarır
        
        Args:
            user_id: Çıkarılacak kullanıcının ID'si
        
        Note:
            Kullanıcı yoksa hata vermez (safe removal)
        """
        self.session_cache.pop(user_id, None)

    def is_valid(self, user_id: int, timeout_minutes: int) -> bool:
        """
        Kullanıcının session'ının geçerli olup olmadığını kontrol eder
        
        Args:
            user_id: Kontrol edilecek kullanıcının ID'si
            timeout_minutes: Session timeout süresi (dakika)
        
        Returns:
            bool: Session geçerliyse True, değilse False
        
        Note:
            - Kullanıcı cache'te yoksa False döner
            - Timeout aşılmışsa kullanıcı cache'ten otomatik silinir ve False döner
            - Session geçerliyse True döner
        """
        info = self.session_cache.get(user_id)
        if not info:
            return False
        from datetime import datetime, timedelta
        timeout = timedelta(minutes=timeout_minutes)
        if datetime.now() - info["addition_time"] > timeout:
            self.remove(user_id)
            return False
        return True
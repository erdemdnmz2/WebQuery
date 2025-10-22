"""
Admin Schemas
Pydantic models for admin approval endpoints
"""
from pydantic import BaseModel
from typing import Optional, List

class AdminApprovals(BaseModel):
    """
    Admin onayı bekleyen query bilgisi
    
    Attributes:
        user_id: Query'yi gönderen kullanıcı ID'si
        workspace_id: İlişkili workspace ID'si
        username: Kullanıcı adı
        query: Onay bekleyen SQL query
        database: Hedef veritabanı
        status: Query durumu ("waiting_for_approval", etc.)
        risk_type: Risk tipi (opsiyonel, analyzer'dan gelen)
        servername: Hedef SQL Server (opsiyonel)
    """
    user_id: int
    workspace_id: int
    username: str
    query: str
    database: str
    status: str
    risk_type: Optional[str] = None
    servername: Optional[str] = None

class AdminApprovalsList(BaseModel):
    """Admin onay listesi response şeması"""
    waiting_approvals: List[AdminApprovals]

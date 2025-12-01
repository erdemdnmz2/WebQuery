"""
Admin Schemas
Pydantic models for admin approval endpoints
"""
from pydantic import BaseModel
from typing import Optional, List
from typing import Dict, Any

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


class AdminPreviewResponse(BaseModel):
    """
    Admin tarafından preview (önizleme) sonucu

    Attributes:
        response_type: "data" veya "error"
        data: Satır listesi (her satır bir dict)
        columns: Opsiyonel, sütun isimleri listesi
        row_count: Dönen satır sayısı
        message: Opsiyonel mesaj (ör. "truncated to MAX_ROW_COUNT")
        error: Hata mesajı (varsa)
    """
    response_type: str  # "data" veya "error"
    data: List[Dict[str, Any]]
    columns: Optional[List[str]] = None
    row_count: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ApprovalRequest(BaseModel):
    """
    Admin onay isteği: frontend approve butonundan gönderilecek body

    Attributes:
        show_results: bool - true ise workspace executable yapılacak
    """
    show_results: bool

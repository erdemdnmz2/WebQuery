from pydantic import BaseModel
from typing import Optional, List

class AdminApprovals(BaseModel):
    user_id : int
    workspace_id : int
    username: str
    query: str
    database: str
    status: str
    risk_type: Optional[str] = None
    servername: Optional[str] = None

class AdminApprovalsList(BaseModel):
    waiting_approvals : List[AdminApprovals]

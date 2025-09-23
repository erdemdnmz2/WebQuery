from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from datetime import datetime

# User schema

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    username: str
    is_admin: Optional[bool] = False

class Token(BaseModel):
    access_token: str

class TokenData(BaseModel):
    sub: Optional[str] =  None

# SQL query schema

class SQLQuery(BaseModel):
    servername: str
    database_name: str 
    query: str

class SQLResponse(BaseModel):
    response_type: str
    info: Optional[str] = None
    error: Optional[str] = None
    data: Optional[List[dict]] = None

class MultipleQueryRequest(BaseModel):
    execution_info: List[Dict[str, str]]
    query: str

class MultipleQueryResponse(BaseModel):
    results: list[SQLResponse] 

class DBNamesResponse(BaseModel):
    names: List[str]

class DatabaseInformationResponse(BaseModel):
    db_info: Dict[str, List[str]]

class WorkspaceInfo(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str
    status: str

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str

class WorkspaceList(BaseModel):
    workspaces: List[WorkspaceInfo]

class WorkspaceUpdate(BaseModel):
    query: str

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
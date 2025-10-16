from fastapi import Depends, FastAPI, HTTPException, status, Response, Request
from fastapi.responses import FileResponse
from database import get_app_db, init_engine_cache ,get_session, close_engines, get_db_info_db, get_db_info_by_user_id
import schemas
import crud
import auth
from crud import create_login_log, update_login_log
from auth import get_current_user
from contextlib import asynccontextmanager
import config
import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from middlewares import AuthMiddleware
from database import session_cache, add_user_to_cache, engine_cache, get_db_info, close_user_engines
from datetime import datetime
from cryptography.fernet import Fernet

#TODO fernet ile session cache şifreleme yap

session_key = Fernet.generate_key()

f = Fernet(session_key)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_app_db() as db:
        await init_engine_cache()
        await get_db_info()
    yield
    await close_engines()

app = FastAPI(lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(AuthMiddleware)

@app.get("/", response_class=FileResponse)
def homepage(current_user = Depends(get_current_user)):
    return FileResponse("templates/home.html")

@app.get("/index", response_class=FileResponse)
def index_page_direct(current_user = Depends(get_current_user)):
    return FileResponse("templates/index.html")

@app.get("/home", response_class=FileResponse)
def index_page(current_user = Depends(get_current_user)):
    return FileResponse("templates/index.html")

@app.get("/login", response_class=FileResponse)
def login_page():
    return FileResponse("templates/login.html")

@app.get("/register", response_class=FileResponse)
def register_page():
    return FileResponse("templates/register.html")

@app.get("/admin", response_class=FileResponse)
def admin(current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin privileges required"
        )
    return FileResponse("templates/admin.html")
    
@app.post("/api/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(user: schemas.UserLogin, response: Response, request: Request):
    async with get_app_db() as db:
        authenticated_user = await crud.authenticate_user(db, user.email, user.password)
    
        if not authenticated_user:
            raise HTTPException(status_code=400, detail="User not found")
        user_id = int(authenticated_user.id)
        username = str(authenticated_user.username)
        user_to_login = {"sub": str(user_id)}
        token = auth.create_access_token(user_to_login)

        response.set_cookie(
            key="access_token",
            value=token,
            secure=False,
            samesite="strict", 
            httponly=True,
            max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES
        )
        client_ip = request.client.host
        await create_login_log(db=db, user_id=user_id, client_ip=client_ip)
        sub_dict = {
            "user_password": f.encrypt(user.password.encode()),
            "addition_date": datetime.now()
        }
        session_cache[user_id] = sub_dict

        if user_id not in engine_cache:
            await add_user_to_cache(
                user_id=user_id,
                username=username,
                password=user.password 
            )

        return {"access_token": token}

@app.post("/api/register")
@limiter.limit(config.RATE_LIMITER)        
async def register(user: schemas.UserCreate, response: Response, request: Request):
    async with get_app_db() as db:     
        if await crud.get_user_by_email(db, user.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        register_result = await crud.create_user(db, user)
        
        if register_result["success"]:
            return register_result
        else:
            raise HTTPException(status_code=400, detail="User could not be created")
    
@app.get("/api/me", response_model=schemas.User)
async def read_users_me(current_user = Depends(get_current_user)):
    return schemas.User(
        username=current_user.username,
        is_admin=current_user.is_admin
    )

@app.post("/api/execute_query", response_model=schemas.SQLResponse)
async def execute_query(query_request: schemas.SQLQuery, current_user = Depends(get_current_user)):

    if current_user.id in session_cache:
        encoded_pw = session_cache[current_user.id]["user_password"]
        current_user.password = f.decrypt(encoded_pw).decode()

    async with get_session(current_user, query_request.servername, query_request.database_name) as session:
        data = await crud.execute_query_db(
            query=query_request.query, 
            db=session, 
            user=current_user, 
            server_name=query_request.servername,
            database_name=query_request.database_name,
        )
        return data

@app.get("/api/database_information", response_model=schemas.DatabaseInformationResponse)
async def get_db_info_endpoint(current_user = Depends(get_current_user)):
    if current_user.id not in engine_cache:
        decoded_password = f.decrypt(session_cache[current_user.id]["user_password"]).decode()
        await add_user_to_cache(
            user_id=current_user.id,
            username=current_user.username,
            password=decoded_password
        )
    db_info = get_db_info_by_user_id(current_user.id)
    return {"db_info": db_info}

@app.post("/api/logout")
async def logout(response: Response, current_user = Depends(get_current_user)):
    response.delete_cookie(
        key="access_token",
        secure=False,
        samesite="strict",
        httponly=True
    )
    async with get_app_db() as db:
        await update_login_log(user_id=current_user.id, db=db)
    await close_user_engines(current_user.id)
    return {"message": "Successfully logged out"}

@app.post("/api/multiple_query", response_model=schemas.MultipleQueryResponse)
async def multiple_query(request: schemas.MultipleQueryRequest, current_user=Depends(get_current_user)):
    if current_user.id in session_cache:
        encoded_pw = session_cache[current_user.id]["user_password"]
        current_user.password = f.decrypt(encoded_pw).decode()
    
    results = []

    if len(request.execution_info) > config.MULTIPLE_QUERY_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {config.MULTIPLE_QUERY_COUNT} queries can be executed at the same time."
        )

    for execution_info in request.execution_info:
        servername = execution_info["servername"]
        database_name = execution_info["database_name"]
        async with get_session(current_user, server_name=servername, database_name=database_name) as session:
            result = await crud.execute_query_db(
                query=request.query,
                db=session,
                user=current_user,
                server_name=servername,
                database_name=database_name
            )
            results.append(result)
        
    return schemas.MultipleQueryResponse(results=results)


@app.post("/api/workspaces")
async def save_workspace(request: schemas.WorkspaceCreate, current_user=Depends(get_current_user)):
    result = await crud.create_workspace(request, current_user.id)
    if result.get("success"):
        return result
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Workspace could not be created."))

@app.get("/api/workspace", response_model= schemas.WorkspaceList)
async def get_workspaces(current_user = Depends(get_current_user)):
    workspaces = await crud.get_workspaces_by_user_id(current_user.id)
    return {"workspaces": workspaces}

@app.delete("/api/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: int, current_user = Depends(get_current_user)):
    if await crud.delete_workspace(workspace_id):
        return Response(status_code=status.HTTP_200_OK)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be deleted.")
    
@app.put("/api/workspaces/{workspace_id}")
async def update_workspace(workspace_id: int, request: schemas.WorkspaceUpdate, current_user = Depends(get_current_user)):
    if await crud.update_workspace(workspace_id, request.query):
        return Response(status_code=status.HTTP_200_OK)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be updated.")
    
@app.get("/api/get_workspace_by_id/{workspace_id}", response_model=schemas.WorkspaceInfo)
async def get_workspace_by_id(workspace_id: int, current_user = Depends(get_current_user)):
    workspace = await crud.get_workspace_by_workspace_id(workspace_id=workspace_id)
    if not workspace or not workspace.query_data:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    workspace_info = schemas.WorkspaceInfo(
        id=workspace.id, 
        name=workspace.name, 
        description=workspace.description, 
        query=workspace.query_data.query,
        servername=workspace.query_data.servername,
        database_name=workspace.query_data.database_name,
        status=workspace.query_data.status
    )
    return workspace_info


@app.get("/api/admin/queries_to_approve", response_model=schemas.AdminApprovalsList)
async def queries_to_approve(current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin privileges required"
        )
    
    waiting_approvals = await crud.get_waiting_queries()
    return {"waiting_approvals": waiting_approvals}

@app.post("/api/admin/approve_query/{workspace_id}")
async def approve_query(workspace_id: int, current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin privileges required"
        )
    
    result = await crud.approve_query_by_workspace_id(workspace_id)
    if result["success"]:
        return result
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Query approval failed")
        )

@app.post("/api/admin/reject_query/{workspace_id}")
async def reject_query(workspace_id: int, current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin privileges required"
        )

    result = await crud.reject_query_by_workspace_id(workspace_id)
    if result["success"]:
        return {"message": "Query rejected successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Query rejection failed")
        )

if __name__ == '__main__':
    uvicorn.run(
        app=app
    )

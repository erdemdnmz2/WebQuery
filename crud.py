from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text, select
from datetime import datetime
from fastapi import Depends
import models, schemas
from database import get_app_db, add_user_to_cache, get_session
from config import message_format, approval_message_format, DANGEROUS_SQL_KEYWORDS
from slack_utils import send_message_to_slack
import uuid
from query_analysis import analyze_query

async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalars().first()

async def create_user(db : AsyncSession, user: schemas.UserCreate):
    created_user = models.User(
        username = user.username,
        email = user.email
    )
    created_user.set_password(user.password)
    db.add(created_user)
    await db.commit()
    await db.refresh(created_user)
    add_user_to_cache(created_user)
    
    return {
        "success": True,
        "message": "Registration successful! Redirecting to login page..."
    }

def verify_password(user: models.User, password: str):
    return user.password == password

async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await get_user_by_email(db, email)
    if not user:
        return False
    try:
        if not user.check_password(password):  # user objesini geç
            return False
    except Exception as e:
        return False
    return user

async def execute_query_db(query: str, db: AsyncSession, user: models.User, server_name: str, database_name: str):
    log_id = None
    async with get_app_db() as db_for_logging:
        log = await create_log(db_for_logging, user, query, machine_name=server_name)
        log_id = log.id
    sql_query = text(query)
    try:
        query_analysis = analyze_query(query)
        
        if query_analysis["return"] == False and not user.is_admin:
            body = approval_message_format.format(
                database_name=database_name,
                username=user.username,
                request_time=datetime.now(),
                query=query,
                risk_type=query_analysis["risk_type"],
                servername = server_name
            )
            send_message_to_slack(body)
            async with get_app_db() as db:
                # Create queryData first
                new_query = models.queryData(
                    user_id = user.id,
                    servername = server_name,
                    database_name = database_name,
                    query = query,
                    uuid = uuid.uuid4(),
                    status = "waiting_for_approval",
                    risk_type = query_analysis["risk_type"]
                )
                db.add(new_query)
                await db.flush()
                
                new_workspace = models.Workspace(
                    user_id=user.id,
                    name=f"Onay Bekleyen Sorgu - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    description=f"Risk türü: {query_analysis['risk_type']} - Admin onayı bekleniyor",
                    query_id=new_query.id
                )
                db.add(new_workspace)
                await db.commit()
            
            result_data = {
                "response_type": "error",
                "data": [],
                "error": "Query found risky, sent for admin approval and saved to your workspace"
            }

            return result_data

        result = await db.execute(sql_query)
        rows = result.fetchall()
        row_count = len(rows)
        
        if row_count > 1000:
            rows = rows[:1000]
            
        result_data = {
            "response_type": "data",
            "data": [dict(row._mapping) for row in rows],
            "message": f"{row_count} rows affected"
        }

        async with get_app_db() as db_for_logging:
            await update_log(db_for_logging, log_id, True, row_count=row_count)

        if row_count > 10000:
            body = message_format.format(
                database_name=database_name,
                username=user.username,
                execution_time=datetime.now(),
                query=query,
                total_rows=row_count
            )
            send_message_to_slack(body)
            
        return result_data
        
    except Exception as e:
        await db.rollback()
        print(f"Error: {str(e)}")
        async with get_app_db() as db_for_logging:
            await update_log(db_for_logging, log_id, False, error=str(e))
        return {"response_type": "error", "data": [], "error": str(e)}

# Logging

async def create_log(db: AsyncSession, user: models.User, query: str, machine_name: str):
    created_log = models.actionLogging(
        user_id = user.id,
        username = user.username,
        query_date = datetime.now(),
        query = query,
        machine_name = machine_name
    )
    db.add(created_log)
    await db.commit()
    await db.refresh(created_log)
    return created_log

async def update_log(db: AsyncSession, log_id, successfull: bool, error : str = None, row_count: int = None):
    result = await db.execute(select(models.actionLogging).where(models.actionLogging.id == log_id))
    log = result.scalars().first()

    if not successfull:
        log.ErrorMessage = error
        log.isSuccessfull = False
    else:
        duration = datetime.now() - log.query_date
        log.ExecutionDurationMS = int(duration.total_seconds() * 1000)
        log.isSuccessfull = True
        log.row_count = row_count
    await db.commit()
    
async def create_login_log(db: AsyncSession, user_id: int, client_ip):
    created_log = models.loginLogging(
        user_id = user_id,
        login_date = datetime.now(),
        client_ip = client_ip
    )
    db.add(created_log)
    await db.commit()

async def update_login_log(user_id: int, db: AsyncSession):
    result = await db.execute(
        select(models.loginLogging)
        .where(models.loginLogging.user_id == user_id)
        .where(models.loginLogging.logout_date.is_(None))
    )
    log = result.scalars().first()
    if log:
        log.logout_date = datetime.now()
        duration = datetime.now() - log.login_date
        log.login_duration_ms = int(duration.total_seconds() * 1000)
        await db.commit()
    else:
        print(f"Active login record for user {user_id}")


def is_query_safe(query: str) -> bool:
    query_words = query.lower().split()
    for keyword in DANGEROUS_SQL_KEYWORDS:
        if keyword in query_words:
            return False
    return True

async def approved_query(query_uuid):
    async with get_app_db() as db:
        results = await db.execute(select(models.queryData).where(models.queryData.uuid == query_uuid))
        query = results.scalars().first()
        if query.status != "waiting":
            send_message_to_slack("Bu sorgu daha önce onaylandı.")
            return {"response_type" : "error", "data": [], "error": "Bu sorgu daha önce onaylandı"}
        user_results = await db.execute(select(models.User).where(models.User.id == query.user_id))
        user = user_results.scalars().first()
    
    async with get_session(server_name=query.servername, database_name=query.database_name, user=user) as session:
        query_results = await session.execute(text(query))
        query_results = query_results.fetchall()

        rows = query_results[:1000]
        row_count = len(query_results)

    response = {
            "response_type": "data",
            "data": [dict(row._mapping) for row in rows],
            "message" : f"{row_count} rows affected"
    }

    async with get_app_db() as db:
        query.status = "executed"

    return response

async def create_workspace(workspace: schemas.WorkspaceCreate, user_id: int):
    async with get_app_db() as db:
        try:
            print(f"Creating workspace with user_id: {user_id}, type: {type(user_id)}")
            print(f"Workspace servername: {workspace.servername}, type: {type(workspace.servername)}")
            print(f"Workspace database_name: {workspace.database_name}, type: {type(workspace.database_name)}")

            # 1. Create queryData object
            new_query_data = models.queryData(
                user_id=user_id,
                servername=workspace.servername,
                database_name=workspace.database_name,
                query=workspace.query,
                uuid=str(uuid.uuid4()),
                status="saved_in_workspace"
            )
            db.add(new_query_data)
            await db.flush()  # Use flush to get the ID before committing

            new_workspace = models.Workspace(
                user_id=user_id,
                name=workspace.name,
                description=workspace.description,
                query_id=new_query_data.id,
            )
            db.add(new_workspace)
            await db.commit()
            await db.refresh(new_workspace)
            return {"success": True, "workspace_id": new_workspace.id}
        except Exception as e:
            await db.rollback()
            print(f"Error creating workspace: {e}")
            return {"success": False, "error": str(e)}
        
async def get_workspaces_by_user_id(user_id: int):
    async with get_app_db() as db:
        results = await db.execute(
            select(models.Workspace).where(models.Workspace.user_id == user_id)
        )
        workspaces = results.scalars().all()
        if not workspaces:
            return []

        query_ids = [ws.query_id for ws in workspaces]

        query_data_results = await db.execute(
            select(models.queryData).where(models.queryData.id.in_(query_ids))
        )
        query_data_map = {qd.id: qd for qd in query_data_results.scalars().all()}

        workspace_list = []
        for ws in workspaces:
            query_data = query_data_map.get(ws.query_id)
            if query_data:
                workspace_list.append(schemas.WorkspaceInfo(
                    id=ws.id,
                    name=ws.name,
                    description=ws.description,
                    query=query_data.query,
                    servername=query_data.servername,
                    database_name=query_data.database_name,
                    status=query_data.status
                ))
        return workspace_list

async def get_workspace_by_workspace_id(workspace_id: int):
    async with get_app_db() as db:
        result = await db.execute(
            select(models.Workspace).where(models.Workspace.id == workspace_id)
        )
        workspace = result.scalars().first()
        
        if workspace:
            query_data_result = await db.execute(
                select(models.queryData).where(models.queryData.id == workspace.query_id)
            )
            workspace.query_data = query_data_result.scalars().first()
            
        return workspace
    
async def delete_workspace(workspace_id: int):
    async with get_app_db() as db:
        try:
            workspace = await db.get(models.Workspace, workspace_id)
            if not workspace:
                return False
            
            query_id = workspace.query_id
            
            await db.delete(workspace)
            
            if query_id:
                query_data = await db.get(models.queryData, query_id)
                if query_data:
                    await db.delete(query_data)
            
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            print(f"Error deleting workspace: {e}")
            return False

async def update_workspace(workspace_id: int, query: str = None, status: str = None):
    async with get_app_db() as db:
        try:
            workspace = await db.get(models.Workspace, workspace_id)
            if not workspace:
                return False
            
            query_data = await db.get(models.queryData, workspace.query_id)
            if not query_data:
                return False
            
            if query:
                query_data.query = query
            
            if status:
                query_data.status = status

            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            print(f"Error updating workspace: {e}")
            return False
        

async def get_waiting_queries():
    async with get_app_db() as db:
        result_list = []
        try:
            results = await db.execute(select(models.queryData).where(models.queryData.status == "waiting_for_approval"))
            queries = results.scalars().all()
            if queries:
                for query in queries:
                   
                    workspace_result = await db.execute(
                        select(models.Workspace).where(models.Workspace.query_id == query.id)
                    )
                    workspace = workspace_result.scalars().first()

                    user = await db.get(models.User, query.user_id)
                    
                    if workspace and user:
                        data = schemas.AdminApprovals(
                            user_id=query.user_id,
                            workspace_id=workspace.id,
                            username = user.username,
                            query= query.query,
                            database=query.database_name,
                            status= query.status,
                            risk_type=query.risk_type,
                            servername=query.servername
                        )

                        result_list.append(data)
            return result_list
        except  Exception as e:
            print(f"Error: {str(e)}")
            return []

async def approve_query_by_workspace_id(workspace_id: int):
    async with get_app_db() as db:
        workspace = await db.get(models.Workspace, workspace_id)
        if not workspace:
            return {"success": False, "error": "Workspace not found"}
            
        query_data = await db.get(models.queryData, workspace.query_id)
        if not query_data:
            return {"success": False, "error": "Query data not found"}
            
        user = await db.get(models.User, query_data.user_id)
        if not user:
            return {"success": False, "error": "User not found"}

    try:
        async with get_session(user, query_data.servername, query_data.database_name) as session:
            sql_query = text(query_data.query)
            result = await session.execute(sql_query)
            rows = result.fetchall()
            row_count = len(rows)

            result_data = [dict(row._mapping) for row in rows]

        async with get_app_db() as db:
            workspace_to_update = await db.get(models.Workspace, workspace_id)
            query_data_to_update = await db.get(models.queryData, query_data.id)
            
            if query_data_to_update:
                query_data_to_update.status = "approved_and_executed"
            if workspace_to_update:
                workspace_to_update.description = f"Admin tarafından onaylandı ve çalıştırıldı - {row_count} satır etkilendi"
            
            await db.commit()
        
        return {
            "success": True,
            "data": result_data,
            "row_count": row_count,
            "query": query_data.query,
            "database": query_data.database_name,
            "servername": query_data.servername
        }
        
    except Exception as e:

        async with get_app_db() as db:
            try:
                workspace_to_update = await db.get(models.Workspace, workspace_id)
                query_data_to_update = await db.get(models.queryData, query_data.id)
                
                if query_data_to_update:
                    query_data_to_update.status = "approval_execution_failed"
                if workspace_to_update:
                    workspace_to_update.description = f"Admin onayladı ancak çalıştırma başarısız: {str(e)}"
                
                await db.commit()
            except Exception as db_error:
                print(f"Durum güncellenirken hata: {db_error}")
        
        print(f"Sorgu onaylanırken hata: {e}")
        return {"success": False, "error": str(e)}

async def reject_query_by_workspace_id(workspace_id: int):
    async with get_app_db() as db:
        try:
            workspace = await db.get(models.Workspace, workspace_id)
            if not workspace:
                return {"success": False, "error": "Workspace not found"}
                
            query_data = await db.get(models.queryData, workspace.query_id)
            if not query_data:
                return {"success": False, "error": "Query data not found"}
            
            query_data.status = "rejected"
            workspace.description = "Admin tarafından reddedildi"
            
            await db.commit()
            return {"success": True}
            
        except Exception as e:
            await db.rollback()
            print(f"Error rejecting query: {e}")
            return {"success": False, "error": str(e)}
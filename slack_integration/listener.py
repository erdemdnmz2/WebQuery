from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_integration.config import SLACK_APP_TOKEN, SLACK_BOT_TOKEN
from app_database.app_database import AppDatabase
from app_database.models import QueryData
from sqlalchemy import select

class SlackListener:
    def __init__(self, app_db: AppDatabase):
        self.app = AsyncApp(token=SLACK_BOT_TOKEN)
        self.app_db = app_db
        self.handler = None
        self.register_handlers()

    def register_handlers(self):
        @self.app.action("approve_with_results")
        async def approve(ack, body, client):
            await self.handle_approve_with_results(ack, body, client)

        @self.app.action("reject_query")
        async def reject(ack, body, client):
            await self.handle_reject_query(ack, body, client)

    async def start(self):
        if not SLACK_APP_TOKEN:
            print("⚠️ SLACK_APP_TOKEN eksik, Slack Socket Mode başlatılamadı.")
            return
            
        self.handler = AsyncSocketModeHandler(self.app, SLACK_APP_TOKEN)
        await self.handler.start_async()

    async def handle_approve_with_results(self, ack, body, client):
        await ack()
        user_id = body["user"]["id"]
        request_id = body["actions"][0]["value"]
        
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            blocks=[],
            text=f"✅ Sorgu <@{user_id}> tarafından onaylandı (Sonuçlar Gösterilecek). (ID: {request_id})"
        )
        
        async with self.app_db.get_app_db() as session:
            try:
                stmt = select(QueryData).where(QueryData.uuid == request_id)
                result = await session.execute(stmt)
                query_data = result.scalar_one_or_none()
                
                if query_data:
                    query_data.status = "APPROVED"
                    await session.commit()
                    print(f"Query {request_id} approved by Slack user {user_id}")
                else:
                    print(f"Query {request_id} not found in database.")
            except Exception as e:
                print(f"Error processing approval for {request_id}: {e}")

    async def handle_reject_query(self, ack, body, client):
        await ack()
        user_id = body["user"]["id"]
        request_id = body["actions"][0]["value"]
        
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            blocks=[],
            text=f"❌ Sorgu <@{user_id}> tarafından reddedildi. (ID: {request_id})"
        )
        
        async with self.app_db.get_app_db() as session:
            try:
                stmt = select(QueryData).where(QueryData.uuid == request_id)
                result = await session.execute(stmt)
                query_data = result.scalar_one_or_none()
                
                if query_data:
                    query_data.status = "REJECTED"
                    await session.commit()
                    print(f"Query {request_id} rejected by Slack user {user_id}")
            except Exception as e:
                print(f"Error processing rejection for {request_id}: {e}")
 
    async def execute_query(self, ack, body, client):
        await ack()

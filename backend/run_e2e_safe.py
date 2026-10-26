from app.core.database import SessionLocal
from app.services.conversation.conversation_service import ConversationService
db = SessionLocal()
service = ConversationService(db)

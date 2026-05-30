import uuid
from sqlalchemy import Column, String, DateTime, Text, Float, Integer, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships - cascade deletes to keep DB clean
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    inference_logs = relationship("InferenceLog", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    inference_logs = relationship("InferenceLog", back_populates="message")


class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    
    model = Column(String(100), nullable=False, index=True)
    provider = Column(String(100), nullable=False, index=True)
    latency_ms = Column(Float, nullable=False, index=True)
    
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    
    status = Column(String(50), nullable=False, index=True)  # "success", "error", "cancelled"
    error_message = Column(Text, nullable=True)
    
    raw_input = Column(Text, nullable=False)  # Prompts/Messages (PII redacted)
    raw_output = Column(Text, nullable=False)  # Response text (PII redacted)
    
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)


    # Relationships
    conversation = relationship("Conversation", back_populates="inference_logs")
    message = relationship("Message", back_populates="inference_logs")

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Conversation & Message Schemas ---
class MessageBase(BaseModel):
    role: str = Field(..., description="Role of the message author: 'user' or 'assistant'")
    content: str = Field(..., description="The markdown text content of the message")

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationBase(BaseModel):
    title: str = Field("New Conversation", description="Custom or automatic title of the chat thread")

class ConversationCreate(ConversationBase):
    pass

class ConversationResponse(ConversationBase):
    id: str
    user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True


# --- SDK Ingestion Schema ---
class IngestLogPayload(BaseModel):
    conversation_id: str = Field(..., description="Unique conversation session UUID")
    message_id: Optional[str] = Field(None, description="Optional associated message UUID")
    model: str = Field(..., description="Model name (e.g. 'gemini-1.5-flash')")
    provider: str = Field(..., description="Model provider (e.g. 'google', 'mock')")
    latency_ms: float = Field(..., description="Model response generation latency in milliseconds")
    prompt_tokens: int = Field(0, description="Tokens used in the system/user prompt")
    completion_tokens: int = Field(0, description="Tokens generated in the model output")
    total_tokens: int = Field(0, description="Prompt + Completion tokens")
    status: str = Field("success", description="Status code ('success', 'error', 'cancelled')")
    error_message: Optional[str] = Field(None, description="Detailed error traceback or message if failed")
    raw_input: str = Field(..., description="Prompt string sent to the model (PII redacted)")
    raw_output: str = Field(..., description="Response output string returned by the model (PII redacted)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context keys")


class InferenceLogResponse(BaseModel):
    id: str
    conversation_id: str
    message_id: Optional[str] = None
    model: str
    provider: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    status: str
    error_message: Optional[str] = None
    raw_input: str
    raw_output: str
    timestamp: datetime

    class Config:
        from_attributes = True


# --- Chat Request Schema ---
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="Conversation ID to continue, or null to start a new one")
    message: str = Field(..., description="New user prompt message")
    model: str = Field("gemini-1.5-flash", description="Model identifier to use")
    provider: str = Field("google", description="Model provider to use: 'google' or 'mock'")

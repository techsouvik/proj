import time
import json
import logging
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, config
from sdk.logger_sdk import inference_logger

# Import Google GenAI if available
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger("ChatAPI")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize Gemini if API key is present
if GENAI_AVAILABLE and config.settings.GEMINI_API_KEY:
    genai.configure(api_key=config.settings.GEMINI_API_KEY)
    logger.info("Google Generative AI successfully configured.")
else:
    logger.info("Running in Mock-fallback mode for LLM generation.")


# --- Mock Responses for Fallback Mode ---
MOCK_ANSWERS = [
    "Hello! I am your AI assistant running locally. Since no Gemini API key is configured yet, I'm streaming a mock reply to show off our ultra-low latency logging system! Feel free to ask me anything.",
    "That is a fascinating question! An ingestion pipeline like this is typically scaled using distributed stream systems (like Kafka) and database sharding to handle thousands of requests per second.",
    "I understand. Modern logging systems must redact PII such as credit cards or SSNs. Let's test it: enter your email or credit card number and check the dashboard to see it masked in real-time!",
    "Yes, our streaming responses are fully cancellation-safe! If you click the 'Stop' button in the UI, the backend event loop will instantly detect the browser disconnection, abort the generation, and log a 'cancelled' status in the database."
]

def get_mock_reply(turn_count: int) -> str:
    idx = turn_count % len(MOCK_ANSWERS)
    return MOCK_ANSWERS[idx]


# --- Conversation Endpoints ---

@router.get("/conversations", response_model=list[schemas.ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    x_session_id: Optional[str] = Header(None)
):
    """Lists all conversation sessions belonging to the session owner, ordered by updated time."""
    query = db.query(models.Conversation)
    if x_session_id:
        query = query.filter(models.Conversation.user_id == x_session_id)
    else:
        query = query.filter(models.Conversation.user_id == None)
    return query.order_by(models.Conversation.updated_at.desc()).all()


@router.post("/conversations", response_model=schemas.ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: schemas.ConversationCreate, 
    db: Session = Depends(get_db),
    x_session_id: Optional[str] = Header(None)
):
    """Creates a new empty chat session owned by the session owner."""
    conversation = models.Conversation(title=payload.title, user_id=x_session_id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{id}", response_model=schemas.ConversationResponse)
def get_conversation(
    id: str, 
    db: Session = Depends(get_db),
    x_session_id: Optional[str] = Header(None)
):
    """Retrieves a single conversation belonging to the session owner with its message history."""
    query = db.query(models.Conversation).filter(models.Conversation.id == id)
    if x_session_id:
        query = query.filter(models.Conversation.user_id == x_session_id)
    else:
        query = query.filter(models.Conversation.user_id == None)
    conversation = query.first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    return conversation


@router.delete("/conversations/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    id: str, 
    db: Session = Depends(get_db),
    x_session_id: Optional[str] = Header(None)
):
    """Deletes a conversation belonging to the session owner and all its cascading messages & logs."""
    query = db.query(models.Conversation).filter(models.Conversation.id == id)
    if x_session_id:
        query = query.filter(models.Conversation.user_id == x_session_id)
    else:
        query = query.filter(models.Conversation.user_id == None)
    conversation = query.first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    db.delete(conversation)
    db.commit()
    return None


# --- Real-Time Streaming & Log Interception Engine ---

@router.post("/stream")
async def stream_chat(
    request: Request,
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    x_session_id: Optional[str] = Header(None)
):
    """
    Primary endpoint for streaming multi-turn chat interactions.
    Leverages Server-Sent Events (SSE), monitors client disconnections (for cancellation telemetry),
    and fires async logging dispatches via the Inference SDK.
    """
    conversation_id = payload.conversation_id

    # 1. Initialize or load Conversation
    if not conversation_id:
        conversation = models.Conversation(
            title=payload.message[:30] + "..." if len(payload.message) > 30 else payload.message,
            user_id=x_session_id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        conversation_id = conversation.id
    else:
        query = db.query(models.Conversation).filter(models.Conversation.id == conversation_id)
        if x_session_id:
            query = query.filter(models.Conversation.user_id == x_session_id)
        else:
            query = query.filter(models.Conversation.user_id == None)
        conversation = query.first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
        # Update conversation timestamp
        conversation.updated_at = models.func.now()
        db.commit()

    # 2. Save User Message to DB
    user_message = models.Message(
        conversation_id=conversation_id,
        role="user",
        content=payload.message
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # 3. Fetch full context history for multi-turn conversations
    past_messages = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(models.Message.created_at.asc()).all()

    # We exclude the newly created user message from history array to avoid duplicates
    history_list = []
    for msg in past_messages[:-1]:
        history_list.append({"role": msg.role, "content": msg.content})

    # Resolve active model & provider
    # Fallback to Mock if key is missing or mock selected explicitly
    use_live_gemini = (
        payload.provider == "google" and 
        GENAI_AVAILABLE and 
        config.settings.GEMINI_API_KEY
    )
    
    active_provider = "google" if use_live_gemini else "mock"
    active_model = payload.model if use_live_gemini else f"mock-{payload.model}"

    # Prepare current prompt & token estimates
    prompt = payload.message
    prompt_tokens = len(prompt) // 4  # Standard token count approximation (4 chars = 1 token)

    if use_live_gemini:
        try:
            # Build full content array (history + current prompt) for accurate token counting
            temp_contents = []
            for h in history_list:
                gemini_role = "model" if h["role"] == "assistant" else "user"
                temp_contents.append({"role": gemini_role, "parts": [{"text": h["content"]}]})
            temp_contents.append({"role": "user", "parts": [{"text": prompt}]})

            model_instance = genai.GenerativeModel(active_model)
            token_count_resp = model_instance.count_tokens(temp_contents)
            prompt_tokens = token_count_resp.total_tokens
            logger.info(f"Gemini API counted exact prompt context tokens: {prompt_tokens}")
        except Exception as token_err:
            logger.warning(f"Failed to count prompt tokens with Gemini API: {token_err}. Using fallback approximation.")

    # Allocate placeholder assistant message in the DB
    assistant_message = models.Message(
        conversation_id=conversation_id,
        role="assistant",
        content=""  # Will fill dynamically
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    async def event_generator():
        start_time = time.time()
        full_response = ""
        log_status = "success"
        error_msg = None
        
        try:
            if use_live_gemini:
                # Live Gemini API implementation with history
                logger.info(f"Invoking Live Gemini API ({active_model})")
                
                # Format history for Gemini SDK
                # Gemini expects: [{'parts': [{'text': '...'}], 'role': 'user'}]
                contents = []
                for h in history_list:
                    # Map roles ("assistant" -> "model")
                    gemini_role = "model" if h["role"] == "assistant" else "user"
                    contents.append({"role": gemini_role, "parts": [{"text": h["content"]}]})
                
                # Add current message
                contents.append({"role": "user", "parts": [{"text": prompt}]})

                try:
                    model_instance = genai.GenerativeModel(active_model)
                    response_stream = await asyncio.to_thread(
                        model_instance.generate_content,
                        contents,
                        stream=True
                    )
                    
                    # Yield chunks as they arrive
                    for chunk in response_stream:
                        # Safety disconnect check inside generation loop!
                        if await request.is_disconnected():
                            log_status = "cancelled"
                            logger.info(f"SSE Streaming cancelled by client for conversation {conversation_id}")
                            break
                        
                        chunk_text = chunk.text
                        full_response += chunk_text
                        yield f"data: {json.dumps({'text': chunk_text, 'conversation_id': conversation_id, 'message_id': assistant_message.id})}\n\n"
                        # Sleep briefly to ensure stream flow pacing
                        await asyncio.sleep(0.02)
                except Exception as ex:
                    log_status = "error"
                    error_msg = str(ex)
                    yield f"data: {json.dumps({'error': error_msg, 'conversation_id': conversation_id})}\n\n"
                    logger.error(f"Error calling live Gemini API: {ex}")
            
            else:
                # Mock Streaming fallback implementation
                # Turn count is represented by length of history / 2
                turn_count = len(history_list) // 2
                reply_text = get_mock_reply(turn_count)
                words = reply_text.split(" ")
                
                logger.info(f"Invoking Mock LLM generator for conversation {conversation_id}")
                
                for word in words:
                    # Detect cancellation immediately in SSE generator loop
                    if await request.is_disconnected():
                        log_status = "cancelled"
                        logger.info(f"Streaming cancellation detected for mock session {conversation_id}")
                        break
                    
                    word_chunk = word + " "
                    full_response += word_chunk
                    yield f"data: {json.dumps({'text': word_chunk, 'conversation_id': conversation_id, 'message_id': assistant_message.id})}\n\n"
                    # Add artificial delay to simulate typing / model latency
                    await asyncio.sleep(0.08)

        except Exception as e:
            log_status = "error"
            error_msg = str(e)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            logger.error(f"General stream error: {e}")

        finally:
            # End timer & record latency
            latency_ms = (time.time() - start_time) * 1000
            completion_tokens = len(full_response) // 4
            
            if use_live_gemini and full_response:
                try:
                    model_instance = genai.GenerativeModel(active_model)
                    completion_tokens_resp = model_instance.count_tokens(full_response)
                    completion_tokens = completion_tokens_resp.total_tokens
                    logger.info(f"Gemini API counted exact completion tokens: {completion_tokens}")
                except Exception as token_err:
                    logger.warning(f"Failed to count completion tokens with Gemini API: {token_err}. Using fallback approximation.")

            # Complete assistant message content update in DB (only if we produced text)
            if full_response:
                try:
                    db.refresh(assistant_message)
                    assistant_message.content = full_response
                    db.commit()
                except Exception as dbe:
                    logger.error(f"Failed to update assistant message content: {dbe}")

            # Schedule near-realtime, non-blocking telemetry log send via the SDK
            # The SDK will automatically handle PII redaction and async background queue dispatching!
            await inference_logger.log_inference_async(
                conversation_id=conversation_id,
                message_id=assistant_message.id,
                model=active_model,
                provider=active_provider,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                status=log_status,
                error_message=error_msg,
                raw_input=prompt,
                raw_output=full_response
            )
            
            # Send terminal stream token
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

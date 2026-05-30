import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app import models, schemas, config

# Redis Queue (RQ) distributed task queue integration
try:
    from redis import Redis
    from rq import Queue
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger("IngestionPipeline")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/logs", tags=["ingestion"])

# Connect to Redis task broker if available, with graceful fallback
redis_conn = None
telemetry_queue = None

if REDIS_AVAILABLE:
    try:
        redis_conn = Redis(
            host=config.settings.REDIS_HOST,
            port=config.settings.REDIS_PORT,
            socket_connect_timeout=2.0
        )
        redis_conn.ping()
        telemetry_queue = Queue("telemetry", connection=redis_conn)
        logger.info(f"Successfully connected to Redis distributed task broker at {config.settings.REDIS_HOST}:{config.settings.REDIS_PORT}")
    except Exception as re:
        logger.warning(f"Could not connect to Redis Task Broker: {re}. Gracefully falling back to FastAPI native in-process BackgroundTasks.")
        redis_conn = None
        telemetry_queue = None


def process_and_save_log(payload_dict: dict):
    """
    Worker function executed in the background to commit the telemetry log.
    Uses a dedicated database session to ensure it's not closed when the HTTP request finishes.
    """
    db = SessionLocal()
    try:
        log_entry = models.InferenceLog(
            conversation_id=payload_dict["conversation_id"],
            message_id=payload_dict.get("message_id"),
            model=payload_dict["model"],
            provider=payload_dict["provider"],
            latency_ms=payload_dict["latency_ms"],
            prompt_tokens=payload_dict["prompt_tokens"],
            completion_tokens=payload_dict["completion_tokens"],
            total_tokens=payload_dict["total_tokens"],
            status=payload_dict["status"],
            error_message=payload_dict.get("error_message"),
            raw_input=payload_dict["raw_input"],
            raw_output=payload_dict["raw_output"]
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        logger.info(f"Log {log_entry.id} saved successfully to Database.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process and store telemetry log: {e}")
    finally:
        db.close()

@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_log(
    payload: schemas.IngestLogPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Accepts log payloads from the Ingestion SDK, performs schema verification,
    and enqueues the log for asynchronous write-to-database processing.
    """
    # Quick sanity check: Verify if the conversation actually exists
    # If the conversation doesn't exist, we might have a stray log, which we can still save 
    # but let's log a warning.
    conversation = db.query(models.Conversation).filter(models.Conversation.id == payload.conversation_id).first()
    if not conversation:
        logger.warning(f"Telemetry log ingested for non-existent conversation {payload.conversation_id}. Creating fallback conversation context.")
        # Create a default conversation context to satisfy DB foreign keys if they are strict
        try:
            fallback_conv = models.Conversation(id=payload.conversation_id, title="Ingested Logs Fallback")
            db.add(fallback_conv)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create fallback conversation: {e}")

    # Enqueue database write to release the client call immediately (near real-time)
    payload_dict = payload.model_dump()
    
    if telemetry_queue is not None:
        try:
            # Enqueue to Redis Task Queue for true thread-isolated worker processing
            telemetry_queue.enqueue("app.api.ingest.process_and_save_log", payload_dict)
            logger.info("Log successfully enqueued to Redis distributed task queue.")
            return {"status": "queued", "message": "Log received and enqueued in Redis Queue."}
        except Exception as q_err:
            logger.error(f"Redis Queue enqueue failed: {q_err}. Falling back to in-process BackgroundTasks.")
            
    # In-process background task queue fallback (local running without Redis)
    background_tasks.add_task(process_and_save_log, payload_dict)
    return {"status": "queued", "message": "Log received and queued for in-process ingestion."}


@router.get("/message/{message_id}", response_model=schemas.InferenceLogResponse)
def get_log_by_message_id(message_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the telemetry log associated with a specific message ID from the database.
    """
    log = db.query(models.InferenceLog).filter(models.InferenceLog.message_id == message_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Inference log not found for this message")
    return log




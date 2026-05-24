import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

logger = logging.getLogger("IngestionPipeline")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/logs", tags=["ingestion"])

def process_and_save_log(payload_dict: dict, db: Session):
    """
    Worker function executed in the background to commit the telemetry log.
    """
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
    background_tasks.add_task(process_and_save_log, payload_dict, db)
    
    return {"status": "queued", "message": "Log received and queued for ingestion."}

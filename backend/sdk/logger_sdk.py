import time
import logging
import asyncio
import httpx
from typing import Optional, Dict, Any
from sdk.pii_redactor import pii_redactor

# Setup logger for the SDK itself
logger = logging.getLogger("InferenceLoggerSDK")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class InferenceLogger:
    """
    A lightweight SDK that wraps LLM calls and dispatches inference telemetry
    to an ingestion service in near real-time, non-blockingly.
    """
    def __init__(self, ingest_url: str = "http://localhost:8000/api/logs/ingest", redact_pii: bool = True):
        self.ingest_url = ingest_url
        self.redact_pii = redact_pii
        # Re-use async client
        self.client = httpx.AsyncClient(timeout=5.0)

    async def close(self):
        """Closes the async client."""
        await self.client.aclose()

    async def log_inference_async(
        self,
        conversation_id: str,
        model: str,
        provider: str,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        status: str,
        raw_input: str,
        raw_output: str,
        message_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Schedules a non-blocking background log ingestion.
        """
        # Formulate payload
        payload = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "model": model,
            "provider": provider,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "status": status,
            "error_message": error_message,
            "raw_input": raw_input,
            "raw_output": raw_output,
            "metadata": metadata or {}
        }

        # Apply PII Redaction if active
        if self.redact_pii:
            payload["raw_input"] = pii_redactor.redact(payload["raw_input"])
            payload["raw_output"] = pii_redactor.redact(payload["raw_output"])

        # Create a background task on the current event loop so we don't block the caller
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._send_log(payload))
        except RuntimeError:
            # Fallback for synchronous/no-event-loop contexts: run in separate thread
            import threading
            def run_in_thread():
                asyncio.run(self._send_log(payload))
            threading.Thread(target=run_in_thread, daemon=True).start()

    async def _send_log(self, payload: Dict[str, Any]):
        """
        Actually dispatches the HTTP post to the ingestion pipeline.
        Handles failures gracefully so the primary LLM call is never disrupted.
        """
        try:
            response = await self.client.post(self.ingest_url, json=payload)
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"Successfully ingested inference log for conversation {payload['conversation_id']}")
            else:
                logger.error(f"Failed to ingest log: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Exceptions occurred while dispatching log to ingestion backend: {e}")


# Global SDK instance
inference_logger = InferenceLogger()

import unittest
import sys
import os
import json

# Ensure parent directory is in sys.path to find 'app' and 'sdk'
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from sdk.pii_redactor import pii_redactor
from sdk.logger_sdk import InferenceLogger
from app.database import Base, engine, SessionLocal
from app import models

class TestAetherSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the DB tables (usually app.db or memory)
        Base.metadata.create_all(bind=engine)

    def test_pii_redaction(self):
        """Tests that the PII redactor properly masks sensitive information."""
        raw_text = (
            "Hi, my email is test.user@example.com and my credit card is "
            "4111111111111111. You can call me at 123-456-7890. "
            "My SSN is 000-12-3456 and my API key is sk-proj-1234567890abcdef1234567890abcdef1234"
        )
        redacted = pii_redactor.redact(raw_text)
        
        self.assertNotIn("test.user@example.com", redacted)
        self.assertNotIn("4111111111111111", redacted)
        self.assertNotIn("123-456-7890", redacted)
        self.assertNotIn("000-12-3456", redacted)
        self.assertNotIn("sk-proj-1234567890abcdef1234567890abcdef1234", redacted)
        
        self.assertIn("[REDACTED_EMAIL]", redacted)
        self.assertIn("[REDACTED_CREDIT_CARD]", redacted)
        self.assertIn("[REDACTED_PHONE]", redacted)
        self.assertIn("[REDACTED_SSN]", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)

    def test_background_task_ingestion_and_retrieval(self):
        """Tests database commit logic for a simulated log entry."""
        db = SessionLocal()
        try:
            # Create a test conversation to satisfy foreign key constraint
            test_conv = models.Conversation(id="test-conv-123", title="Test Conversation")
            db.add(test_conv)
            
            # Create a test message
            test_msg = models.Message(id="test-msg-123", conversation_id="test-conv-123", role="assistant", content="Hello world")
            db.add(test_msg)
            db.commit()

            # Simulate the ingest background worker logic
            log_entry = models.InferenceLog(
                conversation_id="test-conv-123",
                message_id="test-msg-123",
                model="mock-gemini-1.5-flash",
                provider="mock",
                latency_ms=120.5,
                prompt_tokens=10,
                completion_tokens=15,
                total_tokens=25,
                status="success",
                raw_input="Tell me a joke",
                raw_output="Why did the chicken cross the road? To test the pipeline!"
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            # Query and verify the log entry
            saved_log = db.query(models.InferenceLog).filter(models.InferenceLog.message_id == "test-msg-123").first()
            self.assertIsNotNone(saved_log)
            self.assertEqual(saved_log.conversation_id, "test-conv-123")
            self.assertEqual(saved_log.latency_ms, 120.5)
            self.assertEqual(saved_log.total_tokens, 25)
            self.assertEqual(saved_log.status, "success")
            
            # Cleanup test records
            db.delete(saved_log)
            db.delete(test_msg)
            db.delete(test_conv)
            db.commit()
            
        finally:
            db.close()

    def test_session_isolation(self):
        """Tests that conversations are isolated per session/user."""
        db = SessionLocal()
        try:
            # Create conversations for two different sessions, plus a legacy session (null user_id)
            conv1 = models.Conversation(id="conv-session-1", user_id="sess_123", title="Sess 1 Conv")
            conv2 = models.Conversation(id="conv-session-2", user_id="sess_456", title="Sess 2 Conv")
            conv_legacy = models.Conversation(id="conv-session-legacy", user_id=None, title="Legacy Conv")
            
            db.add_all([conv1, conv2, conv_legacy])
            db.commit()
            
            # Query sessions, simulating the API router behavior
            sess_1_query = db.query(models.Conversation).filter(models.Conversation.user_id == "sess_123").all()
            sess_2_query = db.query(models.Conversation).filter(models.Conversation.user_id == "sess_456").all()
            legacy_query = db.query(models.Conversation).filter(models.Conversation.user_id == None).all()
            
            self.assertEqual(len(sess_1_query), 1)
            self.assertEqual(sess_1_query[0].id, "conv-session-1")
            
            self.assertEqual(len(sess_2_query), 1)
            self.assertEqual(sess_2_query[0].id, "conv-session-2")
            
            self.assertEqual(len(legacy_query), 1)
            self.assertEqual(legacy_query[0].id, "conv-session-legacy")
            
            # Clean up
            db.delete(conv1)
            db.delete(conv2)
            db.delete(conv_legacy)
            db.commit()
            
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()

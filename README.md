# 🌌 Aether: Real-Time LLM Observability & Chatbot Ingestion System

Aether is a premium, lightweight, highly performant, and visual-stunning fullstack system designed to log, ingest, and analyze Large Language Model (LLM) inferences in near real-time. It features a responsive, multi-turn AI chatbot interface and an advanced telemetry dashboard to monitor system latency, error rates, model share distributions, and token volumes.

---

## 🚀 Key Features

* **Multi-Turn Chatbot Interface**: Modern, dark-mode first, glassmorphic UI utilizing standard SSE (Server-Sent Events) streaming for realistic, lightning-fast generation.
* **Session-Level Partitioning**: Multi-tenant isolation using unique browser session tracking. Sessions generate a randomized UUID saved to browser `localStorage` and transmit it via `X-Session-ID` request headers, keeping user conversation threads separated. Includes backwards-compatible legacyship for null sessions.
* **Stream Cancellation Support**: Allows users to stop/cancel ongoing model generation instantly. The FastAPI server detects client-side disconnection, halts execution, and logs a `"cancelled"` telemetry status.
* **Enterprise-Grade Token Calculations**: Uses Gemini's native `.count_tokens()` API to accurately calculate prompt context and completion token sizes, with a seamless, silent fallback to character length estimation if running in mock/demo mode.
* **Lightweight Telemetry Logging SDK**: Built as a decoupled, asynchronous module (`backend/sdk`) that intercepts prompt requests and model responses, times execution, evaluates token usage, and sends telemetry logs block-free.
* **PII Redaction Engine**: Fully integrated within the SDK wrapper to redact emails, phone numbers, credit card numbers, Social Security Numbers (SSNs), and API keys before they are ingested or saved to the database.
* **Distributed Task Queue Broker**: Offloads heavy transactional database writes to an asynchronous task queue managed by Redis and Redis Queue (RQ), maintaining low API response latency under high load. Seamlessly falls back to local in-process `BackgroundTasks` if Redis is offline.
* **Active Analytics Caching**: Optimizes the OLAP dashboard path by caching compiled metrics in Redis under a fast 10-second TTL (Time-To-Live), protecting the relational database from frequent UI poll refresh requests.
* **Operational Observability Dashboard**: Beautiful, responsive analytics panel showing cumulative inferences, success rates, average latencies, token volumes, model breakdowns, and recent error audit feeds. Uses **custom interactive SVG vector curves** for graphs to keep compile times ultra-low and animations butter-smooth.
* **Docker Compose One-Command Setup**: Orchestrates an isolated network containing PostgreSQL storage, Redis broker, background RQ worker, FastAPI server, and Next.js client.
* **Seamless Local Fallback**: Gracefully falls back to SQLite for local development (no databases setup required) and mock-streams realistic AI generations if no Gemini API key is configured.

---

## 🏗️ Architectural Topology

```
                  ┌───────────────────────────────────────────────┐
                  │          Next.js Frontend (Port 3000)          │
                  │   ┌───────────────────┐ ┌─────────────────┐   │
                  │   │   Chat UI Panel   │ │ Analytics Graph │   │
                  └───┴─────────┬─────────┴─┴────────┬────────┴───┘
                                │                    │
             Stream (SSE) / REST│                    │ Fetch Metrics
                                ▼                    ▼
                  ┌───────────────────────────────────────────────┐
                  │          FastAPI Backend (Port 8000)          │
                  │   ┌───────────────────┐ ┌─────────────────┐   │
                  │   │  /api/chat/stream │ │ /api/analytics  │   │
                  └───┴─────────┬─────────┴─┴─────────────────┴───┘
                                │
                        Schedules (Async)
                                ▼
                  ┌───────────────────────────────────────────────┐
                  │             Inference Logger SDK              │
                  │   ┌───────────────────────────────────────┐   │
                  │   │  - Measures Latency & Token Speeds    │   │
                  │   │  - Mask PII (Emails, Phones, API Keys)│   │
                  └───┴─────────────────┬─────────────────────┘
                                        │
                             HTTP Ingestion Post
                                        ▼
                  ┌───────────────────────────────────────────────┐
                  │             /api/logs/ingest                  │
                  │  (Enqueues log directly to Background Worker)  │
                  └─────────────────────┬─────────────────────────┘
                                        │
                               Writes (Async)
                                        ▼
                                ┌──────────────┐
                                │  PostgreSQL  │
                                │  (SQLite FS) │
                                └──────────────┘
```

---

## 🗄️ Database Schema Design

We utilize a robust relational database schema designed using SQLAlchemy, supporting CASCADE operations to guarantee clean, orphan-free data deletion.

```
┌─────────────────────────────────┐
│          conversations          │
├─────────────────────────────────┤
│ id: String(36) [PK]             │ 1 ────┐
│ user_id: String(100) [Index]    │       │
│ title: String(255)              │       │ Has Many
│ created_at: DateTime            │       │
│ updated_at: DateTime            │       │
└─────────────────────────────────┘       │
                                          ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│             messages            │   │         inference_logs          │
├─────────────────────────────────┤   ├─────────────────────────────────┤
│ id: String(36) [PK]             │   │ id: String(36) [PK]             │
│ conversation_id: String [FK]    │ 1 │ conversation_id: String [FK]    │
│ role: String(50)                ├─┐ │ message_id: String [FK, Null]   │
│ content: Text                   │ │ │ model: String(100)              │
│ created_at: DateTime            │ │ │ provider: String(100)           │
└─────────────────────────────────┘ │ │ latency_ms: Float               │
                                    │ │ prompt_tokens: Integer          │
                                    │ │ completion_tokens: Integer      │
                                    │ │ total_tokens: Integer           │
                                    │ │ status: String(50)              │
                                    │ │ error_message: Text [Null]      │
                                    │ │ raw_input: Text (Redacted)      │
                                    │ │ raw_output: Text (Redacted)     │
                                    └►│ timestamp: DateTime             │
                                      └─────────────────────────────────┘
```

### Schema Rationale & Tradeoffs
1. **Uncoupled Message & Inference Logging**: Not every message in our database triggers an LLM call (e.g., user questions, or system events). Therefore, `messages` and `inference_logs` are separate entities. `inference_logs` holds a nullable foreign key `message_id` pointing directly to the assistant's generated output, enabling deep granular auditing of specific LLM call outputs.
2. **Cascading Deletions**: Conversations, messages, and telemetry data are structured under foreign key constraints with `ondelete="CASCADE"`. If a conversation is cleared in the UI, all of its nested message histories and logs are automatically and safely deleted, avoiding database bloat.
3. **Redacted Storage**: To fulfill enterprise compliance, `raw_input` and `raw_output` columns store redacted text directly, guaranteeing that raw PII is never stored permanently on disks.
4. **Session-Level Partitioning**: Adding an indexed `user_id` column to conversations isolates threads per browser/tab session. This prevents cross-tenant thread exposure while keeping database schemas clean and compatible with unassigned legacy conversations (where `user_id` is null).

---

## 📦 Getting Started

You can run Aether either using **Docker Compose (Recommended)** or directly on your **Host System**.

### Method 1: Docker Compose (Recommended Setup)
Ensure you have Docker and Docker Compose installed.

1. **Clone & Open Project Workspace**:
   ```bash
   cd /Users/souvikojha/MINE/proj
   ```
2. **Add Gemini Key (Optional)**:
   Create a `.env` file in the root directory (or export it to your environment) if you want to use the live Gemini API:
   ```bash
   echo "GEMINI_API_KEY=your_actual_gemini_key_here" > .env
   ```
   *Note: If no API key is specified, the application will run in standard Demo/Mock mode automatically, providing realistic streaming text for tests.*
3. **Launch the Containerized Stack**:
   ```bash
   docker compose up --build
   ```
   *This boots up the following services on an isolated bridge network:*
   * 🗄️ **`aether_db`**: PostgreSQL 15 container for durable metadata & telemetry logs storage.
   * ⚡ **`aether_redis`**: Redis 7 container serving as the asynchronous task broker and analytics cache.
   * ⚙️ **`aether_backend`**: FastAPI application server processing stream chat SSE and SDK ingestion requests.
   * 👷 **`aether_worker`**: Python RQ (Redis Queue) background worker that handles safe database write operations.
   * 🎨 **`aether_frontend`**: Next.js client hosting our visual telemetry dashboards and interactive chatbot.
4. **Access the Applications**:
   * **Frontend Client (Next.js)**: [http://localhost:3000](http://localhost:3000)
   * **Backend REST API (FastAPI)**: [http://localhost:8000](http://localhost:8000)
   * **Backend Swagger Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Method 2: Host System Running (Local Development)

#### 1. Running the FastAPI Backend
Ensure Python 3.10+ is installed on your Mac.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the backend
python run.py
```
*The backend will automatically create an SQLite file `app.db` and start listening on [http://localhost:8000](http://localhost:8000).*

#### 2. Running the Next.js Frontend
Ensure Node.js 18+ is installed on your Mac.

```bash
cd frontend
npm install
npm run dev
```
*The client will start hot-reloading on [http://localhost:3000](http://localhost:3000).*

#### 3. Running Automated Unit Tests
Aether includes a robust automated test suite in `backend/test_pipeline.py` validating PII redaction patterns, SQLAlchemy cascading relationship delete-orphans, and multi-tenant session isolation queries.

```bash
cd backend
source venv/bin/activate
python test_pipeline.py
```

---

## 🔬 Architectural Decisions & Deep-Dive

### Ingestion Flow & Logging Strategy
Aether prioritizes a decoupled, asynchronous ingestion pipeline to make sure telemetry logging never slows down the end-user's chatbot speed:
1. When a user requests a streaming answer, `app/api/chat.py` initiates the SSE connection.
2. An asynchronous timer measures the start time.
3. As chunks arrive, they are instantly streamed to the frontend browser.
4. If the client disconnects (SSE socket close), we catch the `AbortError` in python, stop generator execution immediately, and mark the log's state as `"cancelled"`.
5. Upon stream completion or abort, the final parameters are recorded.
6. The `InferenceLogger` SDK is called. It applies high-performance regular expressions to mask SSNs, credit cards, phones, emails, and secrets.
7. The SDK dispatches the payload to `/api/logs/ingest` asynchronously using `asyncio.create_task` or background threads.
8. The ingestion service receives the request, runs strict validation using **Pydantic** structures, and queues the payload into FastAPI's native **BackgroundTasks** queue.
9. The client is immediately responded to with `{"status": "queued"}`, freeing the thread pool, while a background process writes the log to the PostgreSQL database safely.

### Failure Handling & Scalability Considerations
* **Swallowing Ingestion Failures**: The SDK uses active exception-swallowing wrappers. If the ingestion microservice goes offline or is congested, the client chat session remains 100% active and unimpacted. Failures are written to local console logs for auditing.
* **SQLite/Postgres Dual Compatibility**: The backend dynamically switches connections depending on database environment strings. It handles threading options and transaction loops database-agnostically, allowing for rapid testing and production-ready deployments.
* **SVG Charting**: Drawing complex metrics lines using heavy third-party ChartJS/Recharts wrapper libraries can introduce compilation failures in Docker (Alpine image node-gyp issues) and increase bundle sizes. We calculated the point coords dynamically in React and rendered them using pure, ultra-modern HTML SVG paths. This guarantees zero external compilation blocks and loads the telemetry graphs instantly!

---

## 📈 Future Improvements (With More Time)

If we were to deploy this system at scale (hundreds of millions of inferences per day), we would introduce the following components:
1. **Distributed Event Brokers (Apache Kafka / RabbitMQ)**: Rather than writing directly from FastAPI's background tasks to Postgres, we would publish telemetry messages to a Kafka queue.
2. **Ingestion Consumers (Go / Rust)**: We would write specialized, hyper-efficient consumers in Rust or Go to pull messages from Kafka in batches and batch-insert them into the database, reducing indexing locks.
3. **Time-Series Optimized Databases (TimescaleDB / ClickHouse)**: Standard Postgres tables can slow down under billions of telemetry rows. We would store `inference_logs` in TimescaleDB (which partitions tables automatically by timestamp) or ClickHouse (optimized for massive analytical queries).
4. **Active Redis Caching**: Aggregated statistics for the dashboard would be pre-calculated every minute and cached in Redis, avoiding direct heavy `SELECT COUNT` calculations on the transactional database.
5. **Active OAuth2 JWT Authentication**: Restrict conversations and analytics visibility under secure user role management.

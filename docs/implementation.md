
# Implementation record

## Stage 1: foundation

Inspected all original source/templates/migrations, Git status, installed tools, and read-only SQLite schema/counts before changing files. Preserved Django 6, the original chat migration, Nova CSS, project entry points, and existing database. Replaced the unfinished auth path and hardcoded import-time agent. Added environment-based settings, dependency manifests, project/config/knowledge/usage/audit models, and additive migrations.

Initial checks: Django system check and three project-boundary tests passed.

## Stage 2: providers, policies, RAG

Added typed provider interface and Ollama/compatible transports, registry, deterministic routing, local embedding interface, bounded atomic text ingestion, and PostgreSQL exact vector search with authorization in the query. Protected KBs and documents independently and retained source lineage for history reauthorization.

## Stage 3: chat and administration

Added quota reservations/settlement, sanitized errors, metadata audit helper, private history, RAG agent/orchestration, and authenticated DRF APIs. Project administrators have scoped configuration endpoints; readers cannot edit them. Test coverage initially reached 39 passing security cases, including capture of actual external HTTP request JSON and denied fallbacks.

## Stage 4: integration and delivery

Updated existing Nova templates and CSS, extracted JavaScript, and added project/history/mode controls with CSRF, safe text rendering, pending states and errors. Added Docker development and disposable database test definitions, a non-root runtime image, CI, seed/demo and explicit legacy adoption commands, and setup/API/architecture documentation.

Additional tests cover transport parsing/streaming/errors, migration preservation, and real PostgreSQL concurrent quota reservations. Portable tests intentionally skip the concurrency check because SQLite does not implement the required row lock.

## Validation scope

Final verification on 2026-09-23:

- Built the final non-root Linux Docker image successfully.
- Ran Django's test runner inside that image against PostgreSQL 17 + pgvector: **55 passed**. This includes migration preservation, exact vector retrieval, two concurrent quota workers, provider transports, and security/API regressions.
- Ran pytest on Windows using SQLite: **54 passed, 1 deliberately skipped** (PostgreSQL row locking).
- Django system checks, migration consistency (`makemigrations --check --dry-run`), Ruff lint/format checks, JavaScript syntax checking, and Compose configuration validation passed.
- Confirmed the original SQLite database still has four conversations/eight messages and only `chat.0001_initial` applied.
- Django tests verify login/chat template rendering. Interactive browser verification was attempted but unavailable: the browser tool reported no available browsers. No visual or interactive browser QA is claimed.

Provider integration tests mock the LangChain model clients and use test embeddings; they do not send prompts to an external provider or download local language models. Real PostgreSQL validation exercises schema migrations, pgvector cosine queries, all application security boundaries, and simultaneous quota reservations. External model quality, CPU capacity, and deployment-specific network configuration require deployment verification.

## Stage 5: LangChain model layer

Replaced the raw chat transports with LangChain's Ollama and Google Generative AI integrations. Added a minimal LangGraph model-execution workflow, leaving model-based routing and `auto` conditions deliberately unimplemented until the routing phase. The local smoke-test default is `qwen2.5:0.5b`; the seeded agent disables RAG so the first CPU-only test needs only one Ollama model. Gemini is configured through `GOOGLE_API_KEY` but remains unavailable while the key is blank.

## Stage 6: Jev automatic routing

Added a second LangGraph workflow for `auto`: sanitize the current user message, bypass Jev for single-mode or credential-bearing requests, otherwise request one typed local/external choice from OpenRouter's `typesafe/jev-1.13`. The decision only reorders already-permitted candidates. Missing credentials, provider errors, malformed responses, and low confidence prefer local; detected secrets prohibit external fallback. Tests capture the exact sanitized decision payload and cover routing, validation, fallback, and secret handling without contacting OpenRouter.

## Stage 7: profiles, group access, and limits

Exposed memberships as project profiles with username/display-name context, retained the existing memberships route for compatibility, and added collective group quota scopes. Usage reservations snapshot all current project groups and enforce every applicable project, user, group, and provider limit. Knowledge bases now accept authorized policy updates, allowing administrators/editors to grant local-data access through the existing group-backed policy system. Cross-project group references and multi-scope quotas fail validation.

## Stage 8: operator admin and test identities

Expanded Django admin into the test control plane. Superusers can add/remove Django users and manage profiles, groups, policies, local knowledge bases, providers, models, agents, and quotas. Quota lists calculate live minute/day request consumption and daily measured-or-reserved tokens for project, profile, group, or provider scope. Security history, usage accounting, and embedding chunks remain read-only. The DEBUG-only `seed_test_access` command creates three environment-password test identities plus representative groups, policies, knowledge bases, and limits without printing the credential.

The original `chatbot/db.sqlite3` is not modified by these test runs. No provider credential is added to source or logs. No existing rows are deleted. The retired `chat/services/ai_agent.py` was the hardcoded prototype integration and is replaced by `chat/agents.py`, `chat/services/orchestration.py`, and `providers/`.

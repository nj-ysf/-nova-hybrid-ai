# REST integration guide

All API routes require authentication. Browser clients use the Django session from `/login/` and send `X-CSRFToken` on writes. Tokens are provisioned by trusted operators with `python chatbot/manage.py drf_create_token USERNAME` and sent as `Authorization: Token YOUR_TOKEN` over HTTPS. Do not place tokens in URLs or browser local storage. Use `drf_create_token -r USERNAME` for operator-driven rotation; these MVP tokens do not expire automatically.

Lists return `{count, next, previous, results}`; `limit` is capped at 100 and `offset` supports paging. No tenant header is accepted: the authenticated user's project membership determines the tenant. Project administrators manage only their project and cannot configure URLs or secret values through the API.

| Endpoint | Methods | Access |
| --- | --- | --- |
| `/api/chat/` | POST | Active project member |
| `/send-message/` | POST | Same secure contract as `/api/chat/` |
| `/api/conversations/` | GET | Caller-owned conversations in active memberships; optional `project_id` filter |
| `/api/conversations/{id}/` | GET | Owner plus current project/source access |
| `/api/conversations/{id}/messages/` | GET | Owner plus current project/source access |
| `/api/projects/` | GET | Caller memberships only |
| `/api/projects/{id}/` | GET, PATCH | Read member; change administrator |
| `/api/knowledge-bases/?project_id={id}` | GET, POST | Read authorized member; create editor |
| `/api/knowledge-bases/{id}/` | GET | Authorized member |
| `/api/knowledge-bases/{id}/documents/` | POST | Authorized editor |
| `/api/projects/{id}/providers/` | GET, POST | Project administrator |
| `/api/projects/{id}/models/` | GET, POST | Project administrator |
| `/api/projects/{id}/agents/` | GET, POST | Project administrator; one configuration per project |
| `/api/projects/{id}/memberships/` | GET, POST | Project administrator |
| `/api/projects/{id}/profiles/` | GET, POST | Project administrator; profile-friendly alias for memberships |
| `/api/projects/{id}/groups/` | GET, POST | Project administrator |
| `/api/projects/{id}/policies/` | GET, POST | Project administrator |
| `/api/projects/{id}/quotas/` | GET, POST | Project administrator |

Configuration collections also support `GET` and `PATCH` at `/{record_id}/`. Deletion is intentionally absent: deactivate memberships or disable providers/models. Tenant/project bootstrap is operator-controlled using ORM management commands; `seed_demo` provides a local starter configuration.

## Chat

```json
{
  "project_id": 1,
  "message": "What is our onboarding process?",
  "mode": "local",
  "classification": 1,
  "knowledge_base_ids": [1]
}
```

`mode` is `auto` (default), `local`, or `external`. `classification` is optional (0–3) and can only raise the effective project/document sensitivity. Optional `conversation_id` resumes a caller-owned conversation in this exact project. Omitting `knowledge_base_ids` searches all authorized project bases; `[]` retrieves none. Messages are limited to 12,000 characters. `stream=true` returns 400 with an explicit unsupported message; chat uses atomic JSON completion in Phase 1.

```json
{
  "reply": "The onboarding process ... [Source 7]",
  "conversation_id": 12,
  "provider": "ollama",
  "model": "qwen2.5:0.5b",
  "sources": [7],
  "usage": {"input_tokens": 240, "output_tokens": 65}
}
```

Source IDs are document IDs from authorized context/lineage. No metadata from unauthorized documents is sent to the provider or included in this response. A citation is model-generated text and should not be interpreted as verified grounding.

## Knowledge

Create a KB with `POST /api/knowledge-bases/?project_id=1`:

```json
{"name": "Employee handbook", "policy": 1}
```

Ingest already-extracted text or Markdown with `POST /api/knowledge-bases/1/documents/`:

```json
{"title": "Onboarding", "text": "New employees complete ...", "policy_id": 1}
```

Successful ingestion returns 201 with document ID/title/chunk count. The document and KB policies must both be accessible to the uploading editor. Limits are 200,000 characters per document and 300,000 bytes per request body. Binary files, URLs, and remote data fetches are not accepted. An embedding outage returns 503 without partial documents.

## Configuration examples

Role values: reader=0, editor=1, administrator=2. Clearance/classification: public=0, internal=1, confidential=2, restricted=3. Administrators remain subject to data clearance and group rules. A project profile is stored as a membership; profile responses also include read-only `username` and `display_name` fields.

```json
{"user": 2, "role": 0, "clearance": 1, "groups": [], "can_use_external": false, "active": true}
```

Create a group, create a policy for that group, then assign it to a local knowledge base:

```json
POST /api/projects/1/groups/
{"name": "Finance"}
```

```json
POST /api/projects/1/policies/
{"name": "Finance data", "minimum_role": 0, "access_level": 1, "classification": 1, "groups": [4]}
```

```json
PATCH /api/knowledge-bases/1/
{"policy": 7}
```

Both the knowledge-base policy and each document policy are enforced. Restricting the knowledge base therefore gates every document inside it, even if an individual document has a broader policy.

A policy combines requirements with AND; listed groups are an OR allowlist:

```json
{"name": "Finance", "minimum_role": 0, "access_level": 2, "classification": 2, "groups": [4]}
```

Provider/model/agent creation, in order (use IDs from prior responses):

```json
{"name": "external-service", "connection_alias": "external", "enabled": true, "available": true}
```

```json
{"provider": 2, "name": "YOUR_GEMINI_MODEL", "context_tokens": 16384, "max_output_tokens": 512, "enabled": true, "supports_streaming": true}
```

```json
{"primary_model": 1, "fallback_model": 2, "system_prompt": "You are a project assistant.", "rag_enabled": true, "top_k": 4, "max_context_chars": 12000}
```

When an agent already exists, PATCH it. To permit external processing, PATCH the project with `{"allow_external": true, "external_max_classification": 1}` and PATCH the relevant membership with `{"can_use_external": true}`. Configuring a fallback alone never grants permission to send data externally.

`auto` uses Jev to prefer `local` or `external` when both modes are permitted and `OPENROUTER_API_KEY` is configured. Jev receives only a sanitized copy of the current message, never history or retrieved context. Missing/unavailable/low-confidence routing prefers local. Explicit `local` or `external` mode bypasses Jev and filters the configured models directly.

Quota examples (one project quota exists after seeding or first chat; PATCH it):

```json
{"requests_per_minute": 20, "requests_per_day": 500, "tokens_per_day": 500000}
```

Add `"user": 2` for a member quota or `"provider": 2` for a provider quota, never both. Missing optional scoped rows inherit project limits. Zero denies. Limits count reservations/fallback attempts as described in [architecture](architecture.md).

Add `"group": 4` instead to create a collective group limit:

```json
{"group": 4, "requests_per_minute": 10, "requests_per_day": 200, "tokens_per_day": 100000}
```

Exactly one of `user`, `group`, or `provider` may be set. A profile in multiple groups must satisfy every applicable group limit as well as the project and optional user/provider limits. Usage records retain the profile's group membership at reservation time so later group changes do not rewrite previous group usage.

No configuration response contains provider keys, database credentials, or connection URLs. A deployment connection alias is an identifier, not a secret.

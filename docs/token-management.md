# API Token Management Guide

This document describes how to configure, rotate, revoke, and limit scopes of API keys for the Kelvin Assistant REST API.

---

## Configuration Overview

Kelvin Assistant uses hashed, scope-limited Bearer tokens to authorize clients (such as the CLI agent or n8n workflows). The server stores token definitions in a JSON configuration file (by default `api-tokens.json`), which is read on startup.

The configuration format looks like this:

```json
{
  "version": 1,
  "tokens": [
    {
      "id": "cli-agent-token",
      "token_sha256": "4a7d762e84d4b3c0be83b27b8782a17726be6df36a87c67c55c5c0c66df36a8b",
      "scopes": ["agent:execute", "agent:write", "agent:approve", "chat:use"]
    },
    {
      "id": "n8n-workflow-token",
      "token_sha256": "8a7f762e92c4b3c0fe83b27c8782a17726be6df36a87c67c55c5c0c66df36a9c",
      "scopes": ["chat:use"]
    }
  ]
}
```

The raw bearer token is shown to the client exactly once when you create it.
Only the `token_sha256` digest is stored in Kelvin configuration.

For production or any LAN-accessible deployment, set:

```text
KELVIN_API_AUTH_MODE=required
KELVIN_API_TOKEN_FILE=/etc/kelvin-assistant/api-tokens.json
```

`KELVIN_API_AUTH_MODE=disabled` is allowed only for local development on a
trusted loopback interface. When auth mode is `required`, Kelvin fails closed at
startup if the token file is missing, malformed, contains plaintext `token`
fields, duplicate identities, duplicate digests, or unknown scopes.

---

## API Scopes and Least Privilege

Always enforce the principle of least privilege when issuing tokens. Only grant the minimum scopes required by a client:

| Scope | Capability | Intended Client |
|---|---|---|
| `system:read` | Query system readiness/health checks. | Monitoring tools. |
| `chat:use` | Send chat messages and stream responses. | Web UI, chat widgets, simple n8n nodes. |
| `knowledge:read` | Query the RAG knowledge base. | Search interfaces. |
| `memory:read` | Read long-term personalization memories. | Memory viewer UI. |
| `memory:write` | Write or update memories. | Personalization controllers. |
| `agent:execute` | Start and plan agent runs. | CLI agent (`kelvin`), advanced workflow loops. |
| `agent:write` | Propose tool executions. | CLI client / background workers. |
| `agent:approve` | Grant explicit approvals for write tools. | Authorized human approval CLI interfaces. |

---

## Token Rotation Procedure

To rotate a token without service interruption:

1. **Generate a New Token**:
   Generate a cryptographically secure random token (e.g. 64 hexadecimal characters):
   ```bash
   # Using openssl
   openssl rand -hex 32
   
   # Using python
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   *Example Token*: `kLV_8a7d9b2c6e4f0a1b3c5d7e9f2a4b6c8d`

2. **Hash the Token**:
   Compute the SHA-256 hash of the generated token:
   ```bash
   echo -n "kLV_8a7d9b2c6e4f0a1b3c5d7e9f2a4b6c8d" | shasum -a 256
   ```
   *Example Digest*: `9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d`

3. **Add the New Token to `api-tokens.json`**:
   Insert the new record into the `tokens` list. Keep the old token intact to prevent downtime:
   ```json
   {
     "id": "cli-agent-token-new",
     "token_sha256": "9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d",
     "scopes": ["agent:execute", "agent:write", "agent:approve", "chat:use"]
   }
   ```

4. **Reload/Restart the Server**:
   Restart the FastAPI backend server to load the updated configuration.

5. **Update the Client Configuration**:
   Update your client (CLI agent environment variables or n8n credentials) to use the new token.

6. **Remove the Old Token**:
   Once you verify the client is successfully communicating with the new token, remove the old token record from `api-tokens.json` and restart the backend server.

Never send the SHA-256 digest as the bearer token. Clients send the raw token;
Kelvin hashes it and compares the digest internally.

---

## Token Revocation

To revoke a compromised or decommissioned API key immediately:

1. Open `api-tokens.json`.
2. Locate the token object containing the target `id` or `token_sha256`.
3. Delete the entire object from the `tokens` array.
4. Restart the FastAPI server.
5. Verify the key is deactivated:
   ```bash
   curl -i -X GET http://127.0.0.1:8000/api/v1/health \
     -H "Authorization: Bearer <revoked-token>"
   ```
   *Expected Response*: `401 Unauthorized` with `Invalid or expired Bearer token.` details.

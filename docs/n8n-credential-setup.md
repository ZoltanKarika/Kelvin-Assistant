# n8n Credential Setup Guide

This guide explains how to configure a scoped Kelvin API token for n8n
workflows. Kelvin stores only SHA-256 token digests in `api-tokens.json`; the
raw token is used only in the n8n credential store and must never be committed.

## 1. Generate a Raw Token

Generate a high-entropy raw token on an admin machine:

```bash
openssl rand -hex 32
```

PowerShell alternative:

```powershell
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
```

Save the raw token directly into your password manager. Do not place it in
Git, workflow JSON, screenshots, issue comments, or documentation.

## 2. Hash the Token

Kelvin expects the SHA-256 digest in `api-tokens.json`.

PowerShell:

```powershell
$token = "<raw-token-from-step-1>"
$bytes = [System.Text.Encoding]::ASCII.GetBytes($token)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
($sha256.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join ""
```

Bash:

```bash
printf '%s' '<raw-token-from-step-1>' | sha256sum
```

## 3. Create the Kelvin Token File

On the Kelvin VM, create `/etc/kelvin-assistant/api-tokens.json` from
`api-tokens.example.json` and replace only the digest values.

Minimal n8n example:

```json
{
  "version": 1,
  "tokens": [
    {
      "id": "n8n-research",
      "token_sha256": "<sha256-of-raw-token>",
      "scopes": ["system:read", "chat:use", "memory:read"]
    }
  ]
}
```

Important rules:

- Use `token_sha256`, not a plaintext `token` field.
- Keep the real `api-tokens.json` outside Git. It is ignored by `.gitignore`.
- Grant only the scopes the workflow needs.
- Do not give n8n `agent:approve`; local approval remains Kelvin's safety
  boundary.

Recommended ownership on the Kelvin VM:

```bash
sudo install -d -o root -g kelvin -m 0750 /etc/kelvin-assistant
sudo install -o root -g kelvin -m 0640 api-tokens.json \
  /etc/kelvin-assistant/api-tokens.json
```

## 4. Configure Kelvin Assistant

Production or LAN-accessible Kelvin deployments must require API auth:

```text
KELVIN_API_AUTH_MODE=required
KELVIN_API_TOKEN_FILE=/etc/kelvin-assistant/api-tokens.json
```

`KELVIN_API_AUTH_MODE=disabled` is for local development only. When auth mode is
`required`, Kelvin fails closed at startup if the token file is missing or
malformed.

Restart Kelvin after changing token configuration:

```bash
sudo systemctl restart kelvin-api
sudo systemctl status kelvin-api --no-pager
```

## 5. Create the n8n Credential

In the n8n UI, create a new **HTTP Header Auth** credential:

- **Header Name:** `Authorization`
- **Header Value:** `Bearer <raw-token-from-step-1>`

The raw token belongs only in the n8n credential store. Exported n8n workflow
JSON must not contain it.

## 6. Test the Credential

Run the n8n health-check workflow or call a read-only Kelvin endpoint with the
credential. A token with `system:read` can call system health/readiness routes.

Expected outcomes:

- `200 OK`: token is valid and has the required scope.
- `401 Unauthorized`: token is missing, malformed, unknown, or revoked.
- `403 Forbidden`: token is valid but lacks the required scope.

## 7. Configure Secondary Credentials Securely

Workflows running on the n8n automation VM often require access to secondary or
external AI services. Keep those credentials in n8n's native credential store,
not in workflow JSON or Kelvin config.

Use minimal privileges:

- Google Gemini API: use a dedicated key for the required models only.
- OpenAI or Anthropic API: use restricted project/service keys and provider-side
  spending limits.
- Every external model request should retain an `X-Correlation-ID` so provider
  usage can be cross-referenced with Kelvin audit logs.

## Troubleshooting

- **Kelvin does not start:** check that `KELVIN_API_TOKEN_FILE` points to a
  readable JSON file with `version: 1`, unique `id` values, valid
  `token_sha256` digests, and known scopes.
- **401 Unauthorized:** confirm n8n sends `Authorization: Bearer <raw-token>`,
  not the SHA-256 digest.
- **403 Forbidden:** add only the missing required scope to that token record,
  then restart Kelvin.

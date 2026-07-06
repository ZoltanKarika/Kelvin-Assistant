# n8n Credential Setup Guide

This guide explains how to configure a Kelvin API token in n8n to allow workflows to authenticate with the Kelvin API.

## 1. Create the API Token File

On the Kelvin VM, create a file named `api-tokens.json`. This file will contain the API tokens that n8n will use to authenticate.

Refer to the `api-tokens.example.json` file in the root of the Kelvin Assistant repository for the correct format.

**Example `api-tokens.json`:**

```json
{
  "tokens": [
    {
      "token": "your-secret-token-here",
      "description": "n8n workflow token",
      "scopes": ["chat:use"]
    }
  ]
}
```

## 2. Configure Kelvin Assistant

In the `.env` file on the Kelvin VM, set the following variables:

```
KELVIN_API_AUTH_MODE=required
KELVIN_API_TOKEN_FILE=/path/to/your/api-tokens.json
```

Replace `/path/to/your/api-tokens.json` with the actual path to the `api-tokens.json` file you created in the previous step.

## 3. Restart Kelvin Assistant

Restart the Kelvin Assistant service for the changes to take effect.

## 4. Create n8n Credential

In the n8n UI, create a new "HTTP Header Auth" credential:

-   **Header Name:** `Authorization`
-   **Header Value:** `Bearer your-secret-token-here`

Replace `your-secret-token-here` with the token value from your `api-tokens.json` file.

## 5. Test the Credential

To test the credential, manually run the "Health Check" workflow in n8n. If the credential is set up correctly, the workflow should execute successfully.

## 6. Configure Secondary Credentials Securely

Workflows running on the n8n automation VM often require access to secondary/external AI services (such as Google Gemini, OpenAI, or Anthropic) to extract update details or draft codebase improvements. To ensure maximum safety and alignment with the Kelvin Security Model:

1. **Use n8n's Native Credential Store**: Never hardcode API keys, passwords, or tokens in workflow nodes or workflow JSON exports. Instead, use the native credentials manager inside the n8n UI (e.g., "Google Gemini API", "OpenAI API", or "Anthropic API").
2. **Minimal Privileges / Least Privilege Principle**:
   - **Google Gemini API**: Create a dedicated API key via Google AI Studio. Restrict it to the specific models needed (e.g., `gemini-1.5-flash`). If possible, restrict the API key's HTTP referrer or IP address to the n8n automation VM's external IP.
   - **OpenAI / Anthropic API**: Create restricted API keys (project-scoped or service-scoped keys) instead of using organization-wide administrator keys. Define strict monthly spending limits on the provider accounts to prevent denial-of-wallet (DoW) attacks.
3. **Correlation ID Auditing**: Every external model request triggered via an n8n workflow retains the `X-Correlation-ID` header. If a secondary provider key is compromised or misused, check the provider billing logs and cross-reference timestamps with Kelvin's `X-Correlation-ID` inside the security audit database table.

## Troubleshooting

-   **401 Unauthorized:** This error indicates that the token is missing or invalid. Double-check that the `Authorization` header and token value are correct in your n8n credential.
-   **403 Forbidden:** This error means the token is valid, but it lacks the required scope for the requested operation. Ensure that the `scopes` array in your `api-tokens.json` file includes the necessary permissions for the workflow.


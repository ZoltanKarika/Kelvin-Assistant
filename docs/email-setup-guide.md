# Kelvin Assistant - Email Notification Setup Guide

This guide explains how to configure and test email notifications in Kelvin Assistant, supporting both **Local SMTP** servers and **n8n Automation Webhooks**.

---

## 1. Provider Modes

Kelvin support two notification provider modes:
1. **SMTP (Direct)**: Connects directly to an external or local SMTP server using python `smtplib`.
2. **n8n (Delegated)**: Calls the configured `n8n` webhook endpoint to let your n8n workflow handle the email templates and delivery.

---

## 2. Local SMTP Server Configuration

For local development or testing, you can use a mock SMTP server like **Mailpit** or **Mailhog**.

### Using Mailpit (Recommended)

1. Run Mailpit in a docker container:
   ```bash
   docker run -d -p 8025:8025 -p 1025:1025 axllent/mailpit
   ```
2. Navigate to Kelvin **Settings** (`/ui/settings`):
   * **SMTP Host**: `localhost`
   * **SMTP Port**: `1025`
   * **SMTP Username**: Leave empty (no auth required for local Mailpit)
   * **SMTP Password**: Leave empty
   * **TLS titkosítás**: Unchecked
   * **Feladó címe**: `kelvin@localhost`
   * **Címzett címe**: `your-email@example.com`
3. Click **Módosítások mentése**, then click **Teszt e-mail küldése** to verify.
4. Open the Mailpit web UI at `http://localhost:8025` to inspect the test email.

---

## 3. n8n-based Email Delivery

If you set **Értesítési Mód (Provider)** to `n8n Automációs webhook`, email notifications are forwarded to your n8n workflows.

1. Set up an n8n webhook listener node expecting:
   * **Method**: `POST`
   * **Path**: `/email-notification` (or similar)
2. The payload sent by Kelvin contains:
   ```json
   {
     "type": "approval_required",
     "run_id": "uuid-here",
     "recipient": "user@example.com",
     "subject": "Kelvin Assistant Approval Required",
     "body": "Detailed notification body text..."
   }
   ```
3. Attach an n8n "Gmail" or "Send Email" node to forward this notification to the user.

---

## 4. Environment Variables Reference

If you prefer to configure email notifications directly via `.env` files, use the following variables:

```ini
# Enable/Disable all notifications
KELVIN_EMAIL_NOTIFICATIONS_ENABLED=true

# Notification Provider ("smtp" or "n8n")
KELVIN_EMAIL_PROVIDER_MODE=smtp

# SMTP details
KELVIN_EMAIL_SMTP_HOST=localhost
KELVIN_EMAIL_SMTP_PORT=1025
KELVIN_EMAIL_SMTP_USERNAME=
KELVIN_EMAIL_SMTP_PASSWORD=
KELVIN_EMAIL_SMTP_USE_TLS=false

# Sender & Recipient
KELVIN_EMAIL_SENDER=kelvin@localhost
KELVIN_EMAIL_RECIPIENT=user@example.com

# Daily digest summary time (HH:MM format)
KELVIN_EMAIL_DAILY_SUMMARY_TIME=18:00

# Granular Toggles
KELVIN_EMAIL_ON_APPROVAL_REQUIRED=true
KELVIN_EMAIL_ON_RUN_COMPLETED=true
KELVIN_EMAIL_ON_RUN_FAILED=true
KELVIN_EMAIL_ON_DAILY_SUMMARY=true
```

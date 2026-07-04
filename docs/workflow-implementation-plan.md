# Plan: Implementing the First Researcher Workflow (v0.7)

This document outlines the step-by-step plan to create the first functional researcher workflow in n8n as part of the "v0.7 Safe n8n Foundation" milestone.

## Prerequisites

1.  A running n8n instance on the `kelvin-automation` VM.
2.  A secure, authenticated connection to the Kelvin API is established and tested.
3.  A `read-only` API token for Kelvin has been created and is stored as a credential in n8n.

## Workflow Goal

To automatically fetch information from a pre-defined online source, summarize it using an external AI, have it analyzed by the local Kelvin agent, and present a structured development proposal.

## Step-by-Step Implementation Plan

### 1. Configure Online AI Service Credential

- **Action:** Obtain an API key from your chosen online text AI service (e.g., OpenAI, Google Gemini, Anthropic).
- **Details:**
    - In the n8n UI, navigate to the "Credentials" section.
    - Create a new credential for your chosen AI service.
    - Securely store your API key in the credential fields. This ensures it is not exposed directly in the workflow.

### 2. Workflow Initialization

- **Action:** Create a new, blank workflow in the n8n UI.
- **Details:** Give it a descriptive name, such as "Researcher Workflow v1".

### 3. Trigger Node

- **Action:** Add a trigger to start the workflow.
- **Details:** Start with a **Manual Trigger** node for easy testing. This can be replaced or supplemented with a **Schedule Trigger** (e.g., "run once daily") later.

### 4. Fetch Online Content

- **Action:** Add a node to retrieve data from an external source.
- **Details:**
    - Use the **HTTP Request** node or a specific node for the source (e.g., **RSS Feed Read**).
    - **Configuration:**
        - **URL:** Configure a single, approved URL. For example, a specific tech blog's RSS feed or an API endpoint. This URL should be from the "allowlist" of sources.
        - **Authentication:** If the source requires it, use credentials stored in n8n.

### 5. Process and Normalize Data

- **Action:** Add a **Code** node (or other data manipulation nodes) to process the fetched data.
- **Details:**
    - The goal is to extract the relevant text content for summarization.
    - This might involve filtering out duplicate entries (if using an RSS feed), selecting specific JSON fields, or cleaning up HTML.
    - The output should be a clean string or a structured object containing the text to be summarized.

### 6. Online AI Summarization

- **Action:** Add the node for the chosen online AI service.
- **Details:**
    - **Node:** Use the appropriate node (e.g., `OpenAI`, `Google Gemini`, etc.).
    - **Authentication:** Select the credential you created in Step 1.
    - **Prompt:** Craft a prompt that instructs the AI to summarize the text from the previous step. Example: `"Summarize the following article for a software development team: {{ $json.content }}"`.
    - **Model:** Select a cost-effective and efficient text model.

### 7. Kelvin API Evaluation (Read-Only)

- **Action:** Add an **HTTP Request** node to call the local Kelvin API.
- **Details:** This is the core integration step.
    - **Authentication:** Use the pre-configured generic credential for the Kelvin API `read-only` token.
    - **URL:** `POST <kelvin_vm_ip>:8000/api/v1/chat` (or the relevant agent/chat endpoint).
    - **Body (JSON):** Send the summary from the online AI for local analysis. Craft a prompt for Kelvin.
        ```json
        {
          "message": "Please analyze the following summary based on our local knowledge base and roadmap, and evaluate its relevance for a new development proposal:

{{ $json.summary_from_ai }}"
        }
        ```
    - **Important:** Ensure this node is configured to use the `kelvin:read` scope via the token.

### 8. Format Final Output

- **Action:** Add a **Set** or **Code** node to structure the final output.
- **Details:** Combine the original source link, the AI summary, and Kelvin's analysis into a single, human-readable message.
    - Example Output Structure:
        ```
        ## New Development Proposal
        **Source:** [Link to original article]
        **AI Summary:**
        > {{ $json.summary_from_ai }}
        **Kelvin's Analysis:**
        > {{ $json.kelvin_analysis }}
        ```

### 9. Final Action (Notification)

- **Action:** Add a final node to present the result for human review.
- **Details:** This could be as simple as being the final output of the manual run, or it could be a notification node (e.g., Email, Discord, Slack) for a fully automated process later. For v0.7, viewing the final output in the n8n UI is sufficient.

## Testing and Validation

- Run the workflow manually after configuring each step to ensure it works as expected.
- Verify that the Kelvin API call is successful and uses the `read-only` token.
- Check the Kelvin server logs to confirm the request was received and processed correctly.
- Confirm that the final output is structured and contains all the required information.

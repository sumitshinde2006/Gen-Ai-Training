# KandaGuide LLM integration

## Architecture

`POST /chat` validates a question, retrieves up to five records with the
existing `app.smart_search.smart_search()` function, and passes those
records (including their `source_url` values) to prompt templates in
`prompts/`. `app.llm.generate_response()` selects Groq or Google Gemini
from environment configuration and performs the provider call. The API
validates the generated JSON before returning exactly `answer`,
`confidence`, and `follow_up`.

The provider wrapper is separate from the FastAPI route. Provider and
configuration errors are returned without SDK exception text or secrets.
Unavailable information is stated rather than generated when search has
no results; the dataset is also known not to contain live mandi prices,
weather, or government schemes. Retrieval only searches the variety
records—it does not index the MANAGE reference document.

Prompt loading is provided by `load_chat_prompts(task_version=...)` in
`app/main.py`. It loads the shared `prompts/system.txt` and either
`prompts/task_prompt_v1.txt` or `prompts/task_prompt_v2.txt`. `/chat`
currently uses V1 by default; the function can load V2 independently for
prompt evaluation without duplicating prompt text in Python.

## Supported providers and models

The provider wrapper uses the official Python SDKs: `groq` and
`google-genai`.

When `LLM_MODEL` is blank, the defaults are:

| Provider | Default model ID | Model catalog |
|---|---|---|
| Groq | `openai/gpt-oss-20b` | [Groq supported models](https://console.groq.com/docs/models) |
| Gemini | `gemini-3.5-flash-lite` | [Google Gemini models](https://ai.google.dev/gemini-api/docs/models) |

Model IDs were checked against the providers' published model catalogs on
November 13, 2026. A provider may change model availability; consult its
current catalog before deployment. `LLM_MODEL` can override the default
with a model ID supported by the selected provider.

## Configuration and running

1. Install dependencies from the repository root:

   ```powershell
   .\myenv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Create `.env` from `.env.example` only when it does not already exist:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

   If `.env` already exists, preserve it and edit it in place. Set
   `LLM_PROVIDER`, the matching API key, and optionally `LLM_MODEL`. Keep
   `.env` private and never commit it. The example file contains no
   credentials.
3. Start the API:

   ```powershell
   .\myenv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

   Swagger UI is available at `http://127.0.0.1:8000/docs`.

Switch providers by setting `LLM_PROVIDER=groq` and supplying
`GROQ_API_KEY`, or setting `LLM_PROVIDER=gemini` and supplying
`GEMINI_API_KEY`. The API code does not need to change.

Create a Groq API key in the
[Groq Console API Keys page](https://console.groq.com/keys), or create a
Gemini API key in [Google AI Studio](https://aistudio.google.com/app/apikey).
Copy the key into the matching variable in your local `.env`; do not share
it or add it to source control.

## Chat endpoint

Request:

```json
{"question": "Which onion varieties have good storage life?"}
```

Successful responses have exactly this shape (answer wording depends on
retrieved data and the configured model):

```json
{
  "answer": "A source-grounded answer with source URL references.",
  "confidence": "medium",
  "follow_up": "Would you like to compare the recorded storage details?"
}
```

Questions must contain 3–1000 non-whitespace characters. If the dataset
does not contain relevant information, KandaGuide says so. A provider or
response-format failure returns HTTP 503 with the same three response
fields and a safe message. Empty/invalid questions are rejected by FastAPI
request validation.

## Prompt evaluation

The two task prompts are compared against the exact Q1–Q10 list in
[`how_llms_work.md`](./how_llms_work.md). The evaluation template and
execution status are in [`../eval/prompt_compare.md`](../eval/prompt_compare.md).
No paid model calls are made automatically by tests. Prompt V2 can be
loaded with `load_chat_prompts("v2")`; production `/chat` uses V1.

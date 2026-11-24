# KandaGuide Interview Guide

## 60-second pitch

KandaGuide is an agricultural assistant focused on onion and garlic growing
information. It combines source-grounded retrieval with calculations that need
to be exact. The FastAPI backend serves `/ask` for cited answers and `/agent`
for requests that may need agricultural evidence, a calculation, or both. The
agent uses a structured planner and LangGraph to route requests, while
deterministic Python tools use `Decimal` for profit, revenue, break-even,
storage-loss, and related calculations. When the request is unclear, the
assistant asks for essential missing information instead of inventing it.
Each new request starts with fresh values; previous values are reused only
when the user explicitly refers to them. I focused on separating model
interpretation from arithmetic, keeping agricultural answers evidence-backed,
and testing the routing and calculations without paid API calls.

## Hardest problem: math routed to the storage workflow

**Situation:** A complete profit question could trigger a follow-up asking for
storage months or storage-loss assumptions. Those values were not needed to
calculate profit.

**Task:** Fix the routing and follow-up behavior without removing RAG,
rewriting the application, or allowing an LLM to perform arithmetic.

**Action:** I traced the request through the planner, graph, tools, and
conversation state. The workflow was sending too many calculations through a
storage break-even path, whose inputs differ from a profit calculation. I
added structured intent planning with a local fast path and a constrained
model fallback for less obvious requests. The graph now routes knowledge,
calculation, and mixed requests separately. Python tools validate the
extracted inputs and perform arithmetic deterministically. Each request also
resets stale outputs; past values are considered only when the user explicitly
refers to them.

**Result:** Complete profit requests no longer need storage information, while
genuinely missing values can still trigger a focused follow-up. Regression
tests cover calculations, mixed RAG and calculation requests, context
isolation, and API routes. The latest full validation completed with 119
passing tests and Ruff passing; model calls in unit tests are mocked.

## Ten likely interview questions

### 1. What problem does KandaGuide solve?

It gives onion and garlic growers a way to ask agricultural questions against
the project's source material and to perform practical calculations. The
answer path depends on the request: source-backed questions use retrieval,
while arithmetic uses calculation tools.

### 2. Can you describe the architecture?

The project has a FastAPI backend, a Streamlit UI, agricultural records and
documents, and a RAG pipeline backed by Chroma. `/ask` handles source-based
questions. `/agent` uses a LangGraph workflow to classify the request, choose
RAG, a calculation tool, or both, and assemble the response.

### 3. Why use RAG instead of fine-tuning?

The agricultural answers need to stay tied to the project's documents and
records, and should include citations or acknowledge when support is missing.
RAG lets the application retrieve that evidence at request time without
baking changing source material into model weights.

### 4. How does the agent choose a tool?

It creates a structured plan with an intent such as calculation, knowledge,
mixed, or clarification. Common, unambiguous calculations use a local fast
path. Less obvious requests can use the configured model to classify intent
and extract stated values. The model is not trusted to calculate or invent
missing inputs; Python validates the plan before execution.

### 5. How do you keep calculations reliable?

The calculation tools use Python `Decimal` arithmetic and explicit unit
conversion. They validate required values, percentage totals, and invalid
denominators, and return a calculation breakdown. Missing essential values
lead to a focused follow-up rather than an assumed default.

### 6. How do you keep agricultural answers grounded?

Knowledge requests use the existing retrieval pipeline. Retrieved source
passages inform the response, and the API returns citations. If supporting
evidence is unavailable, the system can abstain instead of making an
unsupported claim.

### 7. How do you prevent stale conversation data from affecting a new
calculation?

The graph resets per-request answer, citation, and tool-output state. Prior
values are not automatically merged into a new request. The planner receives
prior values only when the user explicitly refers to earlier context, and
only the referenced fields are reused.

### 8. What was the hardest bug, and how did you solve it?

The hardest bug was a complete profit request being routed through
storage-break-even logic, causing irrelevant questions about storage months
and loss. I traced the workflow, separated calculation intent from tool
requirements, added deterministic calculation routing, and covered the
behavior with regression tests. I also addressed stale values in the
conversation state so a correct route would not still use the wrong inputs.

### 9. How did you test the system without incurring API costs?

I tested the deterministic tools directly and exercised graph and API
workflows with mocked planner and LLM responses. The suite covers calculation
results, missing inputs, mixed knowledge and math requests, context isolation,
and the `/health`, `/ask`, and `/agent` endpoints. The latest run reported
119 passing tests; Ruff also passed.

### 10. What are the current limitations, and what would you improve next?

Ambiguous requests that do not match the local planner need a configured LLM
provider. The LangGraph `MemorySaver` is process-local, so state is not
durable across restarts or shared across workers. The API also does not yet
provide a user identity layer for authorizing thread IDs. Next, I would
evaluate planner behavior on a broader set of real paraphrases, then add a
persistent checkpointer and authenticated conversation ownership before a
multi-worker deployment.

"""LangGraph implementation of KandaGuide's bounded agent workflow.

Requires the ``langgraph`` package listed in requirements.txt. MemorySaver is
local in-memory state; restarting the process clears conversation checkpoints.
"""

from __future__ import annotations

import operator
import re
from typing import Annotated, Any, TypedDict

from app.agent_loop import _is_calculation, _needs_rag, _variety_loss, extract_inputs
from app.rag import answer_question
from app.tools import ToolInputError, storage_break_even

try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt
except ImportError as error:  # pragma: no cover - environment dependent
    raise ImportError("LangGraph support requires `pip install -r requirements.txt`.") from error


class AgentState(TypedDict, total=False):
    message: str
    messages: Annotated[list[str], operator.add]
    wants_rag: bool
    wants_calculation: bool
    needs_approval: bool
    tools_used: list[str]
    citations: list[dict[str, Any]]
    rag_answer: str
    calculation_result: dict[str, Any] | None
    answer: str
    follow_up: dict[str, Any] | None
    status: str
    approval_decision: str | None
    error: str | None
    history_text: str


def build_graph(*, rag_fn=answer_question, checkpointer=None):
    """Compile workflow with a per-thread checkpoint and interrupt approval."""
    memory = checkpointer or MemorySaver()
    builder = StateGraph(AgentState)

    def understand_request(state: AgentState) -> dict[str, Any]:
        msg = state.get("message", "")
        messages = state.get("messages", [])
        # Build history from all messages except the current one so routing
        # can see prior context (e.g. a previous follow-up calculation request).
        prior = messages[:-1] if messages else []
        history_text = " ".join(prior)
        combined = (history_text + " " + msg).strip()

        # If the current message alone looks like a calculation, use it.
        # Otherwise check whether the full history+message together look like
        # a calculation continuation (e.g. user replied "3 months" after the
        # agent asked for missing storage duration).
        is_calc = _is_calculation(msg) or _is_calculation(combined)
        needs_rag = _needs_rag(msg) if not is_calc else bool(re.search(
            r"\b(variet(?:y|ies)|disease|fusarium|DOGR|MANAGE|documented|"
            r"agricultural facts?|storage method|how to store|cultivation|season)\b",
            msg, re.I,
        ))
        return {
            "wants_rag": needs_rag,
            "wants_calculation": is_calc,
            "needs_approval": bool(re.search(r"\b(should|recommend|decide|store)\b", combined, re.I)),
            "tools_used": [], "citations": [], "calculation_result": None,
            "follow_up": None, "error": None, "status": "running",
            "history_text": history_text,
        }

    def retrieve_agricultural_context(state: AgentState) -> dict[str, Any]:
        try:
            result = rag_fn(state.get("message", ""))
            return {"rag_answer": result.get("answer", "I don't know."), "citations": result.get("citations", []), "tools_used": state.get("tools_used", []) + ["rag"]}
        except Exception:
            return {"rag_answer": "Agricultural retrieval is temporarily unavailable; no unsupported fact was substituted.", "citations": [], "error": "RAG unavailable", "tools_used": state.get("tools_used", []) + ["rag"]}

    def decide_tool(state: AgentState) -> str:
        if state.get("wants_rag"):
            return "retrieve_agricultural_context"
        if state.get("wants_calculation"):
            return "calculate_storage_break_even"
        return "generate_response"

    def after_retrieval(state: AgentState) -> str:
        return "calculate_storage_break_even" if state.get("wants_calculation") else "generate_response"

    def calculate_storage_break_even(state: AgentState) -> dict[str, Any]:
        full_text = state.get("history_text", "") + " " + state.get("message", "")
        values = extract_inputs(full_text)
        missing = [
            key for key in ("quantity_quintals", "todays_price_per_quintal", "months_of_storage")
            if values[key] is None
        ]
        if missing:
            return {
                "follow_up": {
                    "missing_inputs": missing,
                    "question": (
                        "Please provide: "
                        + ", ".join(m.replace("_", " ") for m in missing)
                        + ". An explicit loss percentage is preferred because the available generic range is unverified."
                    ),
                },
                "tools_used": state.get("tools_used", []) + ["storage_break_even"],
            }
        try:
            variety_citation = None
            if values["expected_storage_loss_percent"] is None:
                variety_loss, variety_citation = _variety_loss(full_text, values["months_of_storage"])
                values["expected_storage_loss_percent"] = variety_loss
            result = storage_break_even(
                quantity_quintals=values["quantity_quintals"],
                todays_price_per_quintal=values["todays_price_per_quintal"],
                months_of_storage=values["months_of_storage"],
                expected_storage_loss_percent=values["expected_storage_loss_percent"],
                additional_costs=values.get("additional_costs"),
                expected_selling_price_per_quintal=values.get("expected_selling_price_per_quintal"),
                loss_source_citation=variety_citation,
            )
        except ToolInputError as error:
            return {"error": str(error), "tools_used": state.get("tools_used", []) + ["storage_break_even"]}
        return {
            "calculation_result": result,
            "citations": state.get("citations", []) + result.get("loss_source_citations", []),
            "tools_used": state.get("tools_used", []) + ["storage_break_even"],
        }

    def generate_response(state: AgentState) -> dict[str, Any]:
        sections = []
        if state.get("rag_answer"):
            sections.append("Source-derived agricultural information:\n" + state["rag_answer"])
        result = state.get("calculation_result")
        if result:
            # Use the full step-by-step narrative if available, else fallback summary
            if result.get("step_by_step"):
                sections.append(result["step_by_step"])
            else:
                be = result.get("break_even_selling_price_per_quintal", "N/A")
                sections.append(
                    f"Break-even selling price: ₹{be}/quintal. "
                    "This is a deterministic calculation, not a source-derived fact."
                )
        follow_up = state.get("follow_up")
        if follow_up:
            sections.append(follow_up["question"])
        error = state.get("error")
        if error and error != "RAG unavailable":
            sections.append("Calculation input error: " + error)
        elif error == "RAG unavailable":
            sections.append("Agricultural retrieval is temporarily unavailable; no unsupported fact was substituted.")
        return {"answer": "\n\n".join(sections) or "Please ask an onion or garlic agricultural question, or request a storage break-even calculation."}

    def approval(state: AgentState) -> dict[str, Any]:
        decision = interrupt({
            "type": "storage_decision_approval",
            "message": "Review the proposed calculation before accepting this storage recommendation.",
            "calculation_result": state.get("calculation_result"),
        })
        normalized = str(decision).strip().lower()
        if normalized not in {"approved", "rejected"}:
            return {"approval_decision": "rejected", "status": "rejected", "answer": "The approval response was invalid; the proposed storage decision was not approved."}
        return {"approval_decision": normalized, "status": "approved" if normalized == "approved" else "rejected"}

    def finalize_response(state: AgentState) -> dict[str, Any]:
        if state.get("status") == "rejected":
            answer = "The proposed storage decision was not approved."
        elif state.get("status") == "approved":
            answer = "The proposed storage decision was approved. " + state.get("answer", "")
        elif state.get("follow_up"):
            answer = state.get("answer", "")
        else:
            answer = state.get("answer", "")
        status = "rejected" if state.get("status") == "rejected" else "completed"
        return {"answer": answer, "status": status}

    builder.add_node("understand_request", understand_request)
    builder.add_node("retrieve_agricultural_context", retrieve_agricultural_context)
    builder.add_node("decide_tool", lambda state: {})
    builder.add_node("calculate_storage_break_even", calculate_storage_break_even)
    builder.add_node("generate_response", generate_response)
    builder.add_node("approval", approval)
    builder.add_node("finalize_response", finalize_response)
    builder.add_edge(START, "understand_request")
    builder.add_edge("understand_request", "decide_tool")
    builder.add_conditional_edges("decide_tool", decide_tool)
    builder.add_conditional_edges("retrieve_agricultural_context", after_retrieval)
    builder.add_edge("calculate_storage_break_even", "generate_response")
    builder.add_conditional_edges("generate_response", lambda s: "approval" if s.get("calculation_result") and s.get("needs_approval") and not s.get("follow_up") else "finalize_response")
    builder.add_conditional_edges("approval", lambda s: "finalize_response")
    builder.add_edge("finalize_response", END)
    return builder.compile(checkpointer=memory)


graph = build_graph()


def invoke(message: str, thread_id: str, *, approval_response: str | None = None) -> dict[str, Any]:
    """Invoke a conversation, or resume its paused approval interrupt."""
    config = {"configurable": {"thread_id": thread_id}}
    if approval_response is not None:
        result = graph.invoke(Command(resume=approval_response), config=config)
    else:
        # Pass only the new message; the Annotated[list, operator.add] reducer
        # appends it to the existing messages list in the checkpoint so the
        # full conversation history is available for follow-up routing.
        result = graph.invoke({"message": message, "messages": [message]}, config=config)
    return result

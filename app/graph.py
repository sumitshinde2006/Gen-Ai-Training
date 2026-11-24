"""LangGraph implementation of KandaGuide's bounded agent workflow.

Requires the ``langgraph`` package listed in requirements.txt. MemorySaver is
local in-memory state; restarting the process clears conversation checkpoints.
"""

from __future__ import annotations

import operator
import re
from typing import Annotated, Any, TypedDict

from app.agent_loop import (
    execute_planned_calculation,
)
from app.agent_planner import plan_agent_request
from app.rag import RAGError, answer_question

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
    calculation_intent: str | None
    plan: dict[str, Any]
    needs_approval: bool
    tools_used: list[str]
    citations: list[dict[str, Any]]
    rag_answer: str | None
    calculation_result: dict[str, Any] | None
    answer: str
    follow_up: dict[str, Any] | None
    status: str
    approval_decision: str | None
    error: str | None
    history_text: str
    request_text: str
    clarification: str | None


def _explicit_context_reference(message: str) -> bool:
    return bool(re.search(
        r"(?:\bsame\b.{0,60}\bbefore\b|as\s+(?:i\s+)?mentioned|"
        r"previous(?:ly)?|earlier|use\s+(?:the\s+)?(?:same|previous)|"
        r"that\s+(?:quantity|price|expense|calculation))\b",
        message,
        re.I,
    ))


def _referenced_history(message: str, prior: list[str]) -> str:
    """Return only the prior calculation values explicitly referenced now."""
    history = " ".join(prior)
    if not history or not _explicit_context_reference(message):
        return ""
    if re.search(
        r"\b(?:same\s+as\s+before|same\s+details|same\s+values|"
        r"previous\s+(?:calculation|values|details)|do\s+it\s+again)\b",
        message,
        re.I,
    ):
        return history

    quantity_ref = bool(re.search(
        r"\b(?:same|previous|earlier|that)\s+(?:total\s+)?"
        r"(?:quantity|amount|stock|volume)\b|"
        r"\b(?:quantity|amount|stock|volume)\b.{0,30}\b(?:same|before|earlier|previous)\b",
        message,
        re.I,
    ))
    price_ref = bool(re.search(
        r"\b(?:same|previous|earlier|that)\s+(?:(?:selling|purchase)\s+)?price\b|"
        r"\bprice\b.{0,30}\b(?:same|before|earlier|previous)\b",
        message,
        re.I,
    ))
    expenses_ref = bool(re.search(
        r"\b(?:same|previous|earlier|those)\s+(?:total\s+)?"
        r"(?:expenses?|costs?)\b|"
        r"\b(?:expenses?|costs?)\b.{0,30}\b(?:same|before|earlier|previous)\b",
        message,
        re.I,
    ))
    if not (quantity_ref or price_ref or expenses_ref):
        return ""

    prior_values = " ".join(prior)
    from app.agent_loop import extract_inputs, extract_profit_inputs

    profit_values = extract_profit_inputs(prior_values)
    storage_values = extract_inputs(prior_values)
    reusable = []
    if quantity_ref:
        if profit_values["quantity_kg"] is not None:
            reusable.append(f"{profit_values['quantity_kg']} kg")
        elif storage_values["quantity_quintals"] is not None:
            reusable.append(f"{storage_values['quantity_quintals']} quintals")
    if price_ref:
        if storage_values["todays_price_per_quintal"] is not None:
            reusable.append(
                f"purchase price ₹{storage_values['todays_price_per_quintal']} per quintal"
            )
        elif profit_values["selling_groups"]:
            reusable.extend(
                f"{group['percentage']}% sold at ₹{group['price_per_kg']}/kg"
                for group in profit_values["selling_groups"]
            )
    if expenses_ref and profit_values["expenses"] is not None:
        reusable.append(f"expenses ₹{profit_values['expenses']}")
    return " ".join(reusable)


def build_graph(*, rag_fn=answer_question, planner_fn=plan_agent_request, checkpointer=None):
    """Compile workflow with a per-thread checkpoint and interrupt approval."""
    memory = checkpointer or MemorySaver()
    builder = StateGraph(AgentState)

    def understand_request(state: AgentState) -> dict[str, Any]:
        msg = state.get("message", "")
        messages = state.get("messages", [])
        # Conversation values are used only when the user explicitly refers to them.
        prior = messages[:-1] if messages else []
        history_text = _referenced_history(msg, prior)
        planning_text = (history_text + " " + msg).strip()
        plan = planner_fn(planning_text)
        intent = plan["intent"]
        operation = plan.get("operation")
        wants_calculation = intent in {"calculation", "mixed"}
        wants_rag = intent in {"knowledge", "mixed"}
        return {
            "wants_rag": wants_rag,
            "wants_calculation": wants_calculation,
            "calculation_intent": operation,
            "plan": plan,
            "request_text": planning_text,
            "clarification": plan.get("clarification"),
            "needs_approval": bool(
                operation == "storage_break_even"
                and re.search(r"\b(should|recommend|decide|store)\b", msg, re.I)
            ),
            "tools_used": [], "citations": [], "rag_answer": None,
            "calculation_result": None, "answer": "",
            "follow_up": None, "error": None, "status": "running",
            "history_text": history_text,
        }

    def retrieve_agricultural_context(state: AgentState) -> dict[str, Any]:
        try:
            plan = state.get("plan", {})
            query = plan.get("knowledge_question") or state.get("message", "")
            result = rag_fn(query)
            return {"rag_answer": result.get("answer", "I don't know."), "citations": result.get("citations", []), "tools_used": state.get("tools_used", []) + ["rag"]}
        except RAGError:
            return {"rag_answer": "Agricultural retrieval is temporarily unavailable; no unsupported fact was substituted.", "citations": [], "error": "RAG unavailable", "tools_used": state.get("tools_used", []) + ["rag"]}

    def decide_tool(state: AgentState) -> str:
        if state.get("wants_rag"):
            return "retrieve_agricultural_context"
        if state.get("wants_calculation"):
            return "calculate_request"
        return "generate_response"

    def after_retrieval(state: AgentState) -> str:
        return "calculate_request" if state.get("wants_calculation") else "generate_response"

    def calculate_request(state: AgentState) -> dict[str, Any]:
        outcome = execute_planned_calculation(
            state.get("request_text", state.get("message", "")),
            state.get("plan", {}),
        )
        if outcome.get("follow_up"):
            return {
                "follow_up": outcome["follow_up"],
                "tools_used": state.get("tools_used", []) + [outcome["tool"]],
            }
        if outcome.get("error"):
            return {
                "error": outcome["error"],
                "tools_used": state.get("tools_used", []) + [outcome["tool"]],
            }
        result = outcome.get("result")
        return {
            "calculation_result": result,
            "citations": state.get("citations", []) + result.get("loss_source_citations", []),
            "tools_used": state.get("tools_used", []) + [outcome["tool"]],
        }

    def generate_response(state: AgentState) -> dict[str, Any]:
        sections = []
        if state.get("rag_answer"):
            sections.append("Source-derived agricultural information:\n" + state["rag_answer"])
        result = state.get("calculation_result")
        if result:
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
        clarification = state.get("clarification")
        if clarification:
            sections.append(clarification)
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
    builder.add_node("calculate_request", calculate_request)
    builder.add_node("generate_response", generate_response)
    builder.add_node("approval", approval)
    builder.add_node("finalize_response", finalize_response)
    builder.add_edge(START, "understand_request")
    builder.add_edge("understand_request", "decide_tool")
    builder.add_conditional_edges("decide_tool", decide_tool)
    builder.add_conditional_edges("retrieve_agricultural_context", after_retrieval)
    builder.add_edge("calculate_request", "generate_response")
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
        # Retain history for explicit user references; the planner receives
        # prior values only after _referenced_history filters them.
        result = graph.invoke({"message": message, "messages": [message]}, config=config)
    return result

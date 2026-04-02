# multi_agent_workflow.py
"""
Multi-Agent Compliance System using LangGraph
==============================================

Architecture:
  Supervisor Agent  →  decides which specialist to call
       ├── Retrieval Agent      (fetches policy docs + web fallback)
       ├── Compliance Agent     (analyses violations)
       └── Communication Agent  (drafts email + resolves contacts + sends)

Flow:
  User query → Supervisor → Retrieval → Supervisor → Compliance → Supervisor → Communication → Supervisor → Done
"""

import time, json, logging
from typing import TypedDict, Literal
from langgraph.graph import StateGraph
from agent_workflow.tools import retrieve_policy_chunks, send_email_tool
from mcp_client import mcp
from dotenv import load_dotenv
import os
from langchain_groq import ChatGroq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
llm = ChatGroq(temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"), model=LLM_MODEL)

POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300


# ─────────────────────────────────────────────
# 1. SHARED STATE — passed between all agents
# ─────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    query: str
    next_agent: str                # supervisor decides who goes next
    retrieved_chunks: list
    top_score: float
    needs_web: bool
    context: str
    violations: dict
    violations_text: str
    email_draft: dict
    department_contacts: list
    review_task_id: str
    review_decision: str
    send_result: str
    agent_history: list            # tracks which agents ran (for debugging)


# ─────────────────────────────────────────────
# 2. SUPERVISOR AGENT — the orchestrator
# ─────────────────────────────────────────────
def supervisor_agent(state: dict) -> dict:
    """
    Decides which specialist agent should run next.
    Uses simple rule-based logic (you can swap this with an LLM call for more flexibility).
    """
    history = state.get("agent_history", [])
    state["agent_history"] = history

    # Rule-based routing: check what has been done so far
    if "retrieval_agent" not in history:
        state["next_agent"] = "retrieval_agent"
        logger.info("SUPERVISOR → routing to Retrieval Agent")

    elif "compliance_agent" not in history:
        state["next_agent"] = "compliance_agent"
        logger.info("SUPERVISOR → routing to Compliance Agent")

    elif "communication_agent" not in history:
        state["next_agent"] = "communication_agent"
        logger.info("SUPERVISOR → routing to Communication Agent")

    else:
        state["next_agent"] = "done"
        logger.info("SUPERVISOR → all agents finished, marking done")

    return state


def supervisor_router(state: dict) -> str:
    """Returns the next node name based on supervisor's decision."""
    return state.get("next_agent", "done")


# ─────────────────────────────────────────────
# 3. RETRIEVAL AGENT — fetches policy data
# ─────────────────────────────────────────────
def retrieval_agent(state: dict) -> dict:
    """
    Responsible for:
    - Retrieving policy chunks from vector DB
    - Falling back to web/LLM search if retrieval score is low
    """
    q = state["query"]
    logger.info("RETRIEVAL AGENT — searching for: %s", q)

    # Step 1: Retrieve from Pinecone
    chunks = retrieve_policy_chunks(q)
    state["retrieved_chunks"] = chunks
    state["top_score"] = 0.7 if chunks else 0.0
    state["needs_web"] = state["top_score"] < 0.65
    logger.info("RETRIEVAL AGENT — got %d chunks, top_score=%.2f", len(chunks), state["top_score"])

    # Step 2: Web fallback if needed
    if state["needs_web"]:
        logger.info("RETRIEVAL AGENT — low score, using LLM web fallback")
        prompt = f"Search-style summary for: {q}\n(Use public knowledge; return a one-paragraph summary.)"
        resp = llm.invoke(prompt)
        state.setdefault("context", "")
        state["context"] += "\n\nWEB_SUMMARY:\n" + resp.content
        logger.info("RETRIEVAL AGENT — web summary added (%d chars)", len(resp.content))

    # Mark this agent as done
    state.setdefault("agent_history", []).append("retrieval_agent")
    return state


# ─────────────────────────────────────────────
# 4. COMPLIANCE AGENT — analyses violations
# ─────────────────────────────────────────────
def compliance_agent(state: dict) -> dict:
    """
    Responsible for:
    - Analysing retrieved chunks for HR/IT/Legal violations
    - Returning structured violation data
    """
    logger.info("COMPLIANCE AGENT — analysing %d chunks", len(state.get("retrieved_chunks", [])))

    chunks_text = "".join([c["text"] + "\n---\n" for c in state.get("retrieved_chunks", [])])
    prompt = (
        f"You are a compliance analyst. Query: {state['query']}\n\n"
        f"Policy context (top chunks):\n{chunks_text}\n\n"
        "If there are potential HR/IT/Legal issues, list them as JSON:\n"
        '{\n'
        '  "HR": [{"issue":"...", "evidence":["chunk_id","..."]}],\n'
        '  "IT": [...],\n'
        '  "LEGAL": [...]\n'
        '}\n'
    )

    resp = llm.invoke(prompt)
    try:
        state["violations"] = json.loads(resp.content)
        logger.info("COMPLIANCE AGENT — found violations in: %s", list(state["violations"].keys()))
    except Exception:
        state["violations_text"] = resp.content
        logger.warning("COMPLIANCE AGENT — could not parse JSON, stored raw text")

    state.setdefault("agent_history", []).append("compliance_agent")
    return state


# ─────────────────────────────────────────────
# 5. COMMUNICATION AGENT — drafts & sends email
# ─────────────────────────────────────────────
def communication_agent(state: dict) -> dict:
    """
    Responsible for:
    - Drafting an email from violations
    - Resolving department contacts
    - Requesting human review & sending email
    """
    # Step 1: Draft email
    logger.info("COMMUNICATION AGENT — drafting email")
    violations_data = json.dumps(state.get("violations") or state.get("violations_text"))
    prompt = f"""
    Based on violations: {violations_data},
    draft an email (subject + body) with clear evidence citations (use chunk_ids).
    Also identify the target department(s) for the email (e.g. "HR", "IT", "Legal", "Finance", "Admin").
    Return JSON: {{ "department": "HR", "subject": "...", "body": "..." }}
    """
    resp = llm.invoke(prompt)
    try:
        state["email_draft"] = json.loads(resp.content)
    except Exception:
        state["email_draft"] = {"department": "HR", "subject": "Incident", "body": resp.content}
    logger.info("COMMUNICATION AGENT — draft for dept=%s", state["email_draft"].get("department"))

    # Step 2: Resolve contacts
    department = state["email_draft"].get("department", "HR")
    contacts = mcp.call("get_contacts", {"department": department})
    state["department_contacts"] = contacts
    if contacts:
        primary = contacts[0]
        state["email_draft"]["recipient"] = primary["email"]
        logger.info("COMMUNICATION AGENT — recipient=%s", primary["email"])
    else:
        state["email_draft"]["recipient"] = "hr@company.com"
        logger.warning("COMMUNICATION AGENT — no contacts found, using fallback")

    # Step 3: Human review + send
    logger.info("COMMUNICATION AGENT — requesting human review")
    args = state["email_draft"]
    payload = {
        "tool": "send_email_tool",
        "arguments": args,
        "evidence_chunks": [c.get("chunk_id", "") for c in state.get("retrieved_chunks", [])],
        "context": state.get("context", ""),
    }
    task_id = mcp.call("create_review_task", {"payload": payload})["task_id"]
    state["review_task_id"] = task_id
    logger.info("COMMUNICATION AGENT — review task=%s, polling...", task_id[:8])

    start = time.time()
    while True:
        t = mcp.call("get_review_task", {"task_id": task_id})
        if t and t["status"] == "done":
            decision = t["decision"]
            state["review_decision"] = decision
            if decision in ("approve", "edit"):
                new_args = t["payload"].get("arguments", args)
                state["send_result"] = send_email_tool(**new_args)
            else:
                state["send_result"] = "REJECTED_BY_REVIEWER"
            logger.info("COMMUNICATION AGENT — decision=%s", decision)
            break
        if time.time() - start > POLL_TIMEOUT_SECONDS:
            raise TimeoutError("Reviewer timeout")
        time.sleep(POLL_INTERVAL_SECONDS)

    state.setdefault("agent_history", []).append("communication_agent")
    return state


# ─────────────────────────────────────────────
# 6. FINISH NODE
# ─────────────────────────────────────────────
def node_finish(state: dict) -> dict:
    logger.info("FINISH — workflow complete. Agents used: %s", state.get("agent_history", []))
    return state


# ─────────────────────────────────────────────
# 7. BUILD THE MULTI-AGENT GRAPH
# ─────────────────────────────────────────────
#
#  ┌──────────────┐
#  │  supervisor   │◄──────────────────────────────┐
#  └──────┬───────┘                                │
#         │ (routes to next agent)                  │
#         ▼                                        │
#  ┌──────────────────┐   ┌──────────────────┐   ┌─┴────────────────────┐
#  │ retrieval_agent   │   │ compliance_agent  │   │ communication_agent  │
#  └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────────┘
#           │                      │                       │
#           └──────────────────────┴───────────────────────┘
#                          (all return to supervisor)
#
#  When supervisor says "done" → finish node

graph = StateGraph(dict)

# Add all nodes
graph.add_node("supervisor", supervisor_agent)
graph.add_node("retrieval_agent", retrieval_agent)
graph.add_node("compliance_agent", compliance_agent)
graph.add_node("communication_agent", communication_agent)
graph.add_node("finish", node_finish)

# Entry point: always start with supervisor
graph.set_entry_point("supervisor")

# Supervisor routes to the correct agent (or finish)
graph.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "retrieval_agent": "retrieval_agent",
        "compliance_agent": "compliance_agent",
        "communication_agent": "communication_agent",
        "done": "finish",
    },
)

# Each agent returns control to supervisor
graph.add_edge("retrieval_agent", "supervisor")
graph.add_edge("compliance_agent", "supervisor")
graph.add_edge("communication_agent", "supervisor")

# Finish
graph.set_finish_point("finish")

# Compile
multi_agent_workflow = graph.compile()

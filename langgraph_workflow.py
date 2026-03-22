# langgraph_workflow.py
import time, json, logging
from langgraph.graph import StateGraph
from agent_workflow.tools import retrieve_policy_chunks, send_email_tool, get_contacts
from db.review_storage import ReviewStorage
from dotenv import load_dotenv
import os
from langchain_groq import ChatGroq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()  # Load environment variables from .env file

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
client = ChatGroq(temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"), model=LLM_MODEL)
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300

store = ReviewStorage()

# Define the state type as a dict (no TypedDict required)
def node_retrieve(state: dict):
    q = state["query"]
    logger.info("NODE:retrieve - query=%s", q)
    chunks = retrieve_policy_chunks(q)
    state["retrieved_chunks"] = chunks
    state["top_score"] = 0.7 if chunks else 0.0
    state["needs_web"] = state["top_score"] < 0.65
    logger.info("NODE:retrieve - got %d chunks, top_score=%.2f, needs_web=%s", len(chunks), state["top_score"], state["needs_web"])
    return state

def node_web_search(state: dict):
    q = state["query"]
    logger.info("NODE:web_search - falling back to web search for query=%s", q)
    prompt = f"Search-style summary for: {q}\n(Use public knowledge; return a one-paragraph summary.)"
    resp = client.invoke(prompt)
    state.setdefault("context", "")
    state["context"] += "\n\nWEB_SUMMARY:\n" + resp.content
    logger.info("NODE:web_search - received summary (%d chars)", len(resp.content))
    return state

def node_analyse(state: dict):
    logger.info("NODE:analyse - analysing %d chunks for violations", len(state.get('retrieved_chunks', [])))
    chunks_text = ''.join([c['text'] + '\n---\n' for c in state.get('retrieved_chunks', [])])
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
    resp = client.invoke(prompt)
    try:
        state["violations"] = json.loads(resp.content)
        logger.info("NODE:analyse - parsed violations JSON: %s", list(state["violations"].keys()))
    except Exception:
        state["violations_text"] = resp.content
        logger.warning("NODE:analyse - could not parse JSON, stored raw text (%d chars)", len(resp.content))
    return state

def node_summarise(state: dict):
    logger.info("NODE:summarise - drafting email from violations")
    prompt = f"""
    Based on violations: {json.dumps(state.get('violations') or state.get('violations_text') )},
    draft an email (subject + body) with clear evidence citations (use chunk_ids).
    Also identify the target department(s) for the email (e.g. "HR", "IT", "Legal", "Finance", "Admin").
    Return JSON: {{ "department": "HR", "subject": "...", "body": "..." }}
    """
    resp = client.invoke(prompt)
    try:
        state["email_draft"] = json.loads(resp.content)
    except Exception:
        state["email_draft"] = {"department":"HR","subject":"Incident","body":resp.content}
    logger.info("NODE:summarise - email draft dept=%s subject=%s", state["email_draft"].get("department"), state["email_draft"].get("subject"))
    return state

def node_resolve_contacts(state: dict):
    department = state["email_draft"].get("department", "HR")
    logger.info("NODE:resolve_contacts - looking up contacts for department=%s", department)
    contacts = get_contacts(department=department)
    state["department_contacts"] = contacts
    if contacts:
        primary = contacts[0]
        state["email_draft"]["recipient"] = primary["email"]
        logger.info("NODE:resolve_contacts - resolved recipient=%s (%s, %s)",
                     primary["email"], primary["contact_person"], primary["designation"])
    else:
        logger.warning("NODE:resolve_contacts - no contacts found for dept=%s, falling back to hr@company.com", department)
        state["email_draft"]["recipient"] = "hr@company.com"
    return state

# The "sensitive action" node - will create review task and poll for decision
def node_request_send_email(state: dict):
    logger.info("NODE:request_send - creating review task for email approval")
    args = state["email_draft"]
    payload = {
        "tool": "send_email_tool",
        "arguments": args,
        "evidence_chunks": [c.get("chunk_id", "") for c in state.get("retrieved_chunks", [])],
        "context": state.get("context", "")
    }
    task_id = store.create_task(payload)
    state["review_task_id"] = task_id
    logger.info("NODE:request_send - task_id=%s, polling for reviewer decision...", task_id[:8])
    start = time.time()
    while True:
        t = store.get_task(task_id)
        if t and t["status"] == "done":
            decision = t["decision"]
            state["review_decision"] = decision
            if decision == "approve":
                # use provided or original args
                new_args = t["payload"].get("arguments", args)
                state["send_result"] = send_email_tool(**new_args)
            elif decision == "edit":
                new_args = t["payload"].get("arguments", args)
                state["send_result"] = send_email_tool(**new_args)
            else:  # reject
                state["send_result"] = "REJECTED_BY_REVIEWER"
            logger.info("NODE:request_send - decision=%s, result=%s", decision, state["send_result"][:50] if isinstance(state["send_result"], str) else state["send_result"])
            break
        if time.time() - start > POLL_TIMEOUT_SECONDS:
            logger.error("NODE:request_send - reviewer timeout after %ds", POLL_TIMEOUT_SECONDS)
            raise TimeoutError("Reviewer timeout")
        time.sleep(POLL_INTERVAL_SECONDS)
    return state

def node_finish(state: dict):
    logger.info("NODE:finish - workflow complete, decision=%s", state.get("review_decision", "N/A"))
    return state

# Build graph
graph = StateGraph(dict)
graph.add_node("retrieve", node_retrieve)
graph.add_node("web_search", node_web_search)
graph.add_node("analyse", node_analyse)
graph.add_node("summarise", node_summarise)
graph.add_node("resolve_contacts", node_resolve_contacts)
graph.add_node("request_send", node_request_send_email)
graph.add_node("finish", node_finish)

graph.set_entry_point("retrieve")

# conditional edges: after retrieve decide whether to run web_search
graph.add_conditional_edges("retrieve", lambda s: "web_search" if s.get("needs_web") else "analyse", {"web_search":"web_search", "analyse":"analyse"})
graph.add_edge("web_search", "analyse")
graph.add_edge("analyse", "summarise")
graph.add_edge("summarise", "resolve_contacts")
graph.add_edge("resolve_contacts","request_send")
graph.add_edge("request_send", "finish")
graph.set_finish_point("finish")

workflow = graph.compile()
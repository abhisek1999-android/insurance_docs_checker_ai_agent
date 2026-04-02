import streamlit as st
import tempfile
import json

from agent_workflow.ingest import ingest_file
from agent_workflow.embeddings_upsert import upsert_chunks
from multi_agent_workflow import multi_agent_workflow as workflow
from mcp_client import mcp

st.set_page_config(page_title="Policy Compliance System")

st.title("📄 Policy Compliance System")

tab1, tab2, tab3 = st.tabs(["Upload Policy", "Query Policy", "Review Tasks"])
# run streamlit - > streamlit run streamlit_app.py

# -----------------------------
# POLICY INGESTION
# -----------------------------
with tab1:

    st.header("Upload Policy Document")

    uploaded_file = st.file_uploader(
        "Upload Policy (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"]
    )

    if uploaded_file:

        suffix = "." + uploaded_file.name.rsplit(".", 1)[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        if st.button("Process & Store Policy"):

            with st.spinner("Parsing document..."):
                chunks = ingest_file(tmp_path)
                st.success(f"Generated {len(chunks)} chunks")
                st.write("Example chunk")
                st.json(chunks[0])

            with st.spinner("Embedding & storing..."):
                upsert_chunks(chunks)
            st.success("Policy stored successfully!")


# -----------------------------
# QUERY INTERFACE (LangGraph)
# -----------------------------
with tab2:

    st.header("Query Policy Knowledge Base")

    query = st.text_input("Ask a policy question")

    if st.button("Run Compliance Check") and query:

        # Run the LangGraph workflow (blocking — includes human review polling)
        # We run it in a thread so Streamlit doesn't freeze completely
        result_container = st.empty()

        with st.spinner("Running multi-agent workflow (Supervisor → Retrieval → Compliance → Communication)..."):
            result = workflow.invoke({"query": query})

        # Show which agents ran
        if result.get("agent_history"):
            st.subheader("Agent Execution Order")
            for i, agent in enumerate(result["agent_history"], 1):
                st.write(f"**{i}.** {agent.replace('_', ' ').title()}")

        # Show retrieved chunks
        if result.get("retrieved_chunks"):
            st.subheader("Retrieved Policy Sections")
            for i, chunk in enumerate(result["retrieved_chunks"]):
                with st.expander(f"Chunk {i+1} | {chunk.get('chunk_id', '')}"):
                    st.write(chunk.get("text", ""))

        # Show violations
        if result.get("violations"):
            st.subheader("Detected Violations")
            st.json(result["violations"])
        elif result.get("violations_text"):
            st.subheader("Analysis")
            st.write(result["violations_text"])

        # Show email draft
        if result.get("email_draft"):
            st.subheader("Email Draft")
            st.json(result["email_draft"])

        # Show review task status
        if result.get("review_task_id"):
            st.info(f"Review Task ID: {result['review_task_id']}")
            st.write(f"Decision: **{result.get('review_decision', 'pending')}**")
            st.write(f"Result: {result.get('send_result', '')}")


# -----------------------------
# REVIEW TASKS (Human-in-the-loop)
# -----------------------------
with tab3:

    st.header("Pending Review Tasks")

    if st.button("Refresh"):
        st.rerun()

    pending = mcp.call("list_pending_tasks") or {}

    if not pending:
        st.info("No pending tasks.")
    else:
        for task_id, task in pending.items():
            with st.expander(f"Task {task_id[:8]}..."):
                st.json(task["payload"])

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("Approve", key=f"approve_{task_id}"):
                        mcp.call("set_review_decision", {"task_id": task_id, "decision": "approve"})
                        st.success("Approved!")
                        st.rerun()

                with col2:
                    if st.button("Reject", key=f"reject_{task_id}"):
                        mcp.call("set_review_decision", {"task_id": task_id, "decision": "reject"})
                        st.warning("Rejected.")
                        st.rerun()

                with col3:
                    edited_body = st.text_area(
                        "Edit email body",
                        value=task["payload"].get("arguments", {}).get("body", ""),
                        key=f"edit_{task_id}"
                    )
                    if st.button("Edit & Approve", key=f"editapprove_{task_id}"):
                        new_args = task["payload"].get("arguments", {})
                        new_args["body"] = edited_body
                        mcp.call("set_review_decision", {"task_id": task_id, "decision": "edit", "new_args": new_args})
                        st.success("Edited and approved!")
                        st.rerun()

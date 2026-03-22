# tools.py
import os, smtplib, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from agent_workflow.retrieval import coarse_retrieve, rerank_with_llm
from dotenv import load_dotenv
from db.postgre_setup import SessionLocal, DepartmentContact

load_dotenv()
logger = logging.getLogger(__name__)

def retrieve_policy_chunks(query: str, top_k=10):
    matches = coarse_retrieve(query, top_k=20)
    reranked = rerank_with_llm(query, matches, top_n=8)
    return [c["metadata"] for c in reranked]


def get_contacts(department: str = None):
    session = SessionLocal()
    query = session.query(DepartmentContact)
    if department:
        query = query.filter(DepartmentContact.department.ilike(department))
    contacts = query.all()
    session.close()
    return [
        {
            "id": c.id,
            "department": c.department,
            "contact_person": c.contact_person,
            "designation": c.designation,
            "email": c.email,
            "phone": c.phone,
            "extension": c.extension,
            "location": c.location,
        }
        for c in contacts
    ]



def send_email_tool(recipient: str, subject: str, body: str) -> str:
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")

    if not sender_email or not sender_password:
        logger.warning("SMTP credentials not set, falling back to mock")
        return f"MOCK: email sent to {recipient} subject={subject}\n\n{body}"

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        logger.info("Email sent to %s, subject=%s", recipient, subject)
        return f"Email sent successfully to {recipient}"
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return f"Failed to send email: {e}"

# reviewer_api.py
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template
from db.review_storage import ReviewStorage
from pathlib import Path
import uvicorn

app = FastAPI()
store = ReviewStorage()
TEMPLATE = Path("reviewer_ui.html").read_text()

@app.get("/", response_class=HTMLResponse)
def dashboard():
    pending = store.list_pending()
    html = Template(TEMPLATE).render(tasks=pending)
    return HTMLResponse(html)

@app.get("/task/{task_id}", response_class=HTMLResponse)
def view_task(task_id: str):
    task = store.get_task(task_id)
    if not task:
        return HTMLResponse("Not found", status_code=404)
    html = Template(TEMPLATE).render(task=task, task_id=task_id)
    return HTMLResponse(html)

@app.post("/task/{task_id}/decision")
def submit_decision(task_id: str, decision: str = Form(...), comments: str = Form(None), recipient: str = Form(None), subject: str = Form(None), body: str = Form(None)):
    task = store.get_task(task_id)
    if not task:
        return {"ok": False}
    new_args = None
    if decision == "edit":
        new_args = {"recipient": recipient, "subject": subject, "body": body}
    store.set_decision(task_id, decision, new_args=new_args, comments=comments)
    return RedirectResponse("/", status_code=302)

if __name__=="__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
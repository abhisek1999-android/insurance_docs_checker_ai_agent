# review_storage.py
from sqlitedict import SqliteDict
import time, uuid
from dotenv import load_dotenv
import os

load_dotenv()



class ReviewStorage:
    def __init__(self):
        self.db_path = os.getenv("REVIEW_TASK_DB")

    def create_task(self, payload: dict) -> str:
        task_id = str(uuid.uuid4())
        with SqliteDict(self.db_path) as db:
            db[task_id] = {
                "payload": payload,
                "status": "pending",
                "created_at": time.time(),
                "decision": None
            }
            db.commit()
        return task_id

    def get_task(self, task_id: str):
        with SqliteDict(self.db_path) as db:
            return db.get(task_id)

    def set_decision(self, task_id: str, decision: str, new_args: dict = None, comments: str = None):
        with SqliteDict(self.db_path) as db:
            task = db.get(task_id)
            if not task:
                return False
            task["status"]="done"
            task["decision"]=decision
            task["comments"]=comments
            if new_args:
                task["payload"]["arguments"] = new_args
            db[task_id]=task
            db.commit()
            return True

    def list_pending(self):
        with SqliteDict(self.db_path) as db:
            return {k:v for k,v in db.items() if v["status"]=="pending"}
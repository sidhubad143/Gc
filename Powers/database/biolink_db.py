"""
Powers/database/biolink_db.py
"""
from Powers.database import MongoDB


class BioLinkSettings(MongoDB):
    db_name = "biolink_settings"

    def __init__(self):
        super().__init__(self.db_name)

    def _default(self, chat_id: int) -> dict:
        return {
            "chat_id": chat_id,
            "mode": "off",  # off | admin | normal | strict
        }

    def get_mode(self, chat_id: int) -> str:
        doc = self.find_one({"chat_id": chat_id})
        return doc.get("mode", "off") if doc else "off"

    def set_mode(self, chat_id: int, mode: str) -> bool:
        if mode not in ("off", "admin", "normal", "strict"):
            return False
        existing = self.find_one({"chat_id": chat_id})
        if existing:
            self.update({"chat_id": chat_id}, {"$set": {"mode": mode}})
        else:
            self.insert_one({"chat_id": chat_id, "mode": mode})
        return True


class BioLinkApprove(MongoDB):
    db_name = "biolink_approve"

    def __init__(self):
        super().__init__(self.db_name)

    def approve(self, chat_id: int, user_id: int) -> bool:
        if self.is_approved(chat_id, user_id):
            return False
        self.insert_one({"chat_id": chat_id, "user_id": user_id})
        return True

    def unapprove(self, chat_id: int, user_id: int) -> bool:
        if not self.is_approved(chat_id, user_id):
            return False
        self.delete_one({"chat_id": chat_id, "user_id": user_id})
        return True

    def is_approved(self, chat_id: int, user_id: int) -> bool:
        return bool(self.find_one({"chat_id": chat_id, "user_id": user_id}))

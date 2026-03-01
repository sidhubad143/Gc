"""
Powers/database/nsfw_db.py
"""
from datetime import datetime
from Powers.database import MongoDB


class NSFWSettings(MongoDB):
    db_name = "nsfw_settings"

    def __init__(self):
        super().__init__(self.db_name)

    def get_mode(self, chat_id):
        doc = self.find_one({"chat_id": chat_id})
        return doc.get("mode", "off") if doc else "off"

    def set_mode(self, chat_id, mode):
        if mode not in ("off", "soft", "normal", "strict"):
            return False
        existing = self.find_one({"chat_id": chat_id})
        if existing:
            self.update({"chat_id": chat_id}, {"$set": {"mode": mode}})
        else:
            self.insert_one({"chat_id": chat_id, "mode": mode})
        return True

    def is_enabled(self, chat_id):
        return self.get_mode(chat_id) != "off"


class NSFWApprove(MongoDB):
    db_name = "nsfw_approve"

    def __init__(self):
        super().__init__(self.db_name)

    def approve(self, chat_id, user_id, approved_by):
        if self.is_approved(chat_id, user_id):
            return False
        self.insert_one({
            "chat_id": chat_id, "user_id": user_id,
            "approved_by": approved_by, "approved_at": datetime.utcnow()
        })
        return True

    def unapprove(self, chat_id, user_id):
        if not self.is_approved(chat_id, user_id):
            return False
        self.delete_one({"chat_id": chat_id, "user_id": user_id})
        return True

    def is_approved(self, chat_id, user_id):
        return bool(self.find_one({"chat_id": chat_id, "user_id": user_id}))

    def list_approved(self, chat_id):
        return self.find_all({"chat_id": chat_id}) or []


class NSFWViolations(MongoDB):
    db_name = "nsfw_violations"

    def __init__(self):
        super().__init__(self.db_name)

    def add_violation(self, chat_id, user_id, category):
        """
        Fix: MongoDB.update() wraps in $set internally,
        so $inc nahi chal sakda. Manual fetch + increment karo.
        """
        existing = self.find_one({
            "chat_id": chat_id, "user_id": user_id, "category": category
        })
        if existing:
            # Manual increment — $inc nahi, fetch karke +1 karo
            new_count = existing.get("count", 0) + 1
            self.update(
                {"chat_id": chat_id, "user_id": user_id, "category": category},
                {"count": new_count, "last_seen": datetime.utcnow()}
            )
        else:
            self.insert_one({
                "chat_id": chat_id, "user_id": user_id, "category": category,
                "count": 1, "last_seen": datetime.utcnow()
            })

    def get_violations(self, chat_id, user_id):
        return self.find_all({"chat_id": chat_id, "user_id": user_id}) or []

    def get_total(self, chat_id, user_id):
        return sum(d.get("count", 0) for d in self.get_violations(chat_id, user_id))

    def clear_violations(self, chat_id, user_id):
        self.delete_one({"chat_id": chat_id, "user_id": user_id})

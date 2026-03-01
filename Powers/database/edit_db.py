"""
Powers/database/edit_db.py
"""
from Powers.database import MongoDB


class EditSettings(MongoDB):
    db_name = "edit_settings"

    def __init__(self):
        super().__init__(self.db_name)

    def get(self, chat_id: int) -> dict:
        doc = self.find_one({"chat_id": chat_id})
        return doc or {"anti_edit": False, "anti_long": False, "long_limit": 200}

    def _save(self, chat_id: int, key: str, value):
        existing = self.find_one({"chat_id": chat_id})
        if existing:
            self.update({"chat_id": chat_id}, {"$set": {key: value}})
        else:
            data = {"chat_id": chat_id, "anti_edit": False, "anti_long": False, "long_limit": 200}
            data[key] = value
            self.insert_one(data)

    def set_anti_edit(self, chat_id: int, val: bool):
        self._save(chat_id, "anti_edit", val)

    def set_anti_long(self, chat_id: int, val: bool):
        self._save(chat_id, "anti_long", val)

    def set_long_limit(self, chat_id: int, limit: int):
        self._save(chat_id, "long_limit", limit)

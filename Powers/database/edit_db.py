"""
Powers/database/edit_db.py
"""
from Powers.database import MongoDB


class EditSettings(MongoDB):
    db_name = "edit_settings"

    def __init__(self):
        super().__init__(self.db_name)

    def _default(self, chat_id: int) -> dict:
        return {
            "chat_id":   chat_id,
            "anti_edit": "off",   # off | admin | normal | strict
            "anti_long": "off",   # off | admin | normal | strict
            "long_limit": 200,
        }

    def get(self, chat_id: int) -> dict:
        doc = self.find_one({"chat_id": chat_id})
        return doc if doc else self._default(chat_id)

    def _save(self, chat_id: int, key: str, value):
        existing = self.find_one({"chat_id": chat_id})
        if existing:
            self.update({"chat_id": chat_id}, {"$set": {key: value}})
        else:
            data = self._default(chat_id)
            data[key] = value
            self.insert_one(data)

    def set_anti_edit(self, chat_id: int, mode: str):
        """mode: off | admin | normal | strict"""
        self._save(chat_id, "anti_edit", mode)

    def set_anti_long(self, chat_id: int, mode: str):
        """mode: off | admin | normal | strict"""
        self._save(chat_id, "anti_long", mode)

    def set_long_limit(self, chat_id: int, limit: int):
        self._save(chat_id, "long_limit", limit)

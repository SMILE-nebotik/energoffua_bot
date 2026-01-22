from regions.base import BaseRegion

class LvivRegion(BaseRegion):
    code = "lviv"
    name = "Львівська область (в розробці)"
    is_active = False

    def get_groups(self) -> list[str]:
        return ["1.1", "1.2", "2.1", "2.2", "3.1"]

    async def get_schedule(self, group: str, date: str) -> dict | None:
        return None
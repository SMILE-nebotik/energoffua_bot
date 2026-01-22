from regions.base import BaseRegion

class KyivRegion(BaseRegion):
    code = "kyiv"
    name = "Київська область (в розробці)"
    is_active = False # Поки вимкнено

    def get_groups(self) -> list[str]:
        return ["1", "2", "3"] # Тестові групи

    async def get_schedule(self, group: str, date: str) -> dict | None:
        return None
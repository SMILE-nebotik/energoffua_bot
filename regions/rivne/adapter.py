from regions.base import BaseRegion

class RivneRegion(BaseRegion):
    code = "rivne"
    name = "Рівненська область (в розробці)"
    is_active = False

    def get_groups(self) -> list[str]:
        return ["1", "2", "3"]

    async def get_schedule(self, group: str, date: str) -> dict | None:
        return None
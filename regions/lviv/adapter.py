from regions.base import BaseRegion

class LvivRegion(BaseRegion):
    code = "lviv"
    name = "Львівська область"
    is_active = True  # <--- ВМИКАЄМО, щоб з'явився в меню

    def get_groups(self) -> list[str]:
        return ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2"]

    async def get_schedule(self, group: str, date: str) -> dict | None:
        # Поки повертаємо None (даних немає), але бот не впаде
        return None
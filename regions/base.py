from abc import ABC, abstractmethod

class BaseRegion(ABC):
    """
    Абстрактний клас, який повинні наслідувати всі регіони.
    Він гарантує, що бот зможе спілкуватися з будь-якою областю однаково.
    """

    @property
    @abstractmethod
    def code(self) -> str:
        """Унікальний код регіону (напр. 'volyn')"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Назва регіону для меню"""
        pass
    
    @property
    def is_active(self) -> bool:
        """Чи готовий цей регіон до використання"""
        return False

    @abstractmethod
    def get_groups(self) -> list[str]:
        """Повертає список доступних черг (груп)"""
        pass

    @abstractmethod
    async def get_schedule(self, group: str, date: str) -> dict | None:
        """
        Повертає словник:
        {
            'hours': ['on', 'off', ...], (48 значень по 30 хв)
            'updated_at': '12:00'
        }
        або None, якщо даних немає.
        """
        pass
    
    async def update_data(self) -> list[str]:
        """
        Опціональний метод для запуску парсингу.
        Повертає список груп, де змінився графік.
        """
        return []
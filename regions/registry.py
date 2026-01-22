from regions.volyn.adapter import VolynRegion
from regions.lviv.adapter import LvivRegion
from regions.kyiv.adapter import KyivRegion # Припускаємо, що ти створив файли
from regions.rivne.adapter import RivneRegion

# Список всіх реалізованих класів
_regions_list = [
    VolynRegion(),
    LvivRegion(),
    KyivRegion(),
    RivneRegion()
]

# Словник для швидкого пошуку: {'volyn': VolynRegion(), ...}
REGIONS = {r.code: r for r in _regions_list}

def get_region(code: str):
    return REGIONS.get(code)

def get_active_regions_list():
    return [r for r in _regions_list if r.is_active]

def get_all_regions_list():
    return _regions_list
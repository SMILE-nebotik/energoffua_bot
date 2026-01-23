from regions.volyn.adapter import VolynRegion
from regions.lviv.adapter import LvivRegion
from regions.kyiv.adapter import KyivRegion
from regions.rivne.adapter import RivneRegion
from regions import volyn, lviv

# Список всіх реалізованих класів
_regions_list = [
    VolynRegion(),
    LvivRegion(),
    KyivRegion(),
    RivneRegion()
]

# Словник для швидкого пошуку: {'volyn': VolynRegion(), ...}
REGIONS = {
    "volyn": volyn,
    "lviv": lviv,
}
def get_region(code: str):
    return REGIONS.get(code)

def get_active_regions_list():
    return [r for r in _regions_list if r.is_active]

def get_all_regions_list():
    return _regions_list
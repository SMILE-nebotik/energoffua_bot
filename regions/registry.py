from regions.volyn.adapter import VolynRegion
from regions.lviv.adapter import LvivRegion
from regions.kyiv.adapter import KyivRegion


volyn_region = VolynRegion()
lviv_region = LvivRegion()
kyiv_region = KyivRegion()

_regions_list = [
    volyn_region,
    lviv_region,
    kyiv_region
]


REGIONS = {
    "volyn": volyn_region,
    "lviv": lviv_region,
    "kyiv": kyiv_region
}

def get_region(code: str):
    return REGIONS.get(code)

def get_active_regions_list():
    return [r for r in _regions_list if r.is_active]

def get_all_regions_list():
    return _regions_list
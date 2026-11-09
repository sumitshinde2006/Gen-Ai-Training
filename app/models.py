
from dataclasses import dataclass
from typing import Optional


@dataclass
class Record:

    variety_name: str
    category: str
    season: Optional[str]
    maturity_days_after_transplanting: Optional[str]
    yield_t_ha: Optional[str]
    storage_life: Optional[str]
    source_url: str
    maturity_note: Optional[str] = None

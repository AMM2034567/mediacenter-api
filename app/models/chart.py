from typing import Optional, List
from pydantic import BaseModel

class ChartCategory(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    type: str  # "movie" or "tv"

class ChartItem(BaseModel):
    id: str
    title: str
    rate: Optional[str] = None
    cover: Optional[str] = None
    url: Optional[str] = None
    episodes_info: Optional[str] = None
    card_subtitle: Optional[str] = None
    category_id: Optional[str] = None

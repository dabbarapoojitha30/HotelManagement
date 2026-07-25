"""Room database model."""
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, BeforeValidator
from typing_extensions import Annotated

PyObjectId = Annotated[str, BeforeValidator(str)]


class RoomDB(BaseModel):
    id: str = Field(description="Room Number/ID, e.g. 101")
    name: str
    type: str
    price: float
    status: str = "avail"  # "avail", "booked", "maint"
    cls: str = "r1"  # CSS class
    feats: List[str] = Field(default_factory=list)
    fcls: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

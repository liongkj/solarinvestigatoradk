"""Data models for Solar Plant management"""

from pydantic import BaseModel, Field
from typing import List
from enum import Enum
import uuid


class PlantType(str, Enum):
    """Plant type enumeration"""

    FIT = "FiT"  # Feed-in Tariff
    ZERO_EXPORT = "Zero Export"


class Plant(BaseModel):
    """Plant data model"""

    plant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plant_name: str = Field(..., description="Name of the solar plant")
    type: PlantType = Field(..., description="Plant type (FiT or Zero Export)")

    class Config:
        use_enum_values = True


class PlantListResponse(BaseModel):
    """Response model for plant list"""

    plants: List[Plant]
    total: int

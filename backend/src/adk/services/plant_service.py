"""Plant service for managing solar plants"""

import logging
from typing import List, Optional
from adk.models.plant import Plant, PlantType

logger = logging.getLogger(__name__)


class PlantService:
    """Service for managing solar plants"""

    def __init__(self):
        # Initialize with dummy data (TODO: connect to actual database)
        self._dummy_plants = [
            Plant(
                plant_id="9f085080-8061-11ef-a0c8-e34c9d773f6e",
                plant_name="Plant TT",
                type=PlantType.FIT,
            ),
            Plant(
                plant_id="99ecfd00-7fdd-11ef-a0c8-e34c9d773f6e",
                plant_name="Plant P",
                type=PlantType.ZERO_EXPORT,
            ),
            Plant(
                plant_id="452a5270-fc1f-11ec-9d0d-5faa5f7f8fb1",
                plant_name="Plant TH",
                type=PlantType.FIT,
            ),
            Plant(
                plant_id="282fcf50-4e31-11ee-be3c-c169ad1457df",
                plant_name="Plant D",
                type=PlantType.FIT,
            ),
            Plant(
                plant_id="6b855460-e815-11ec-9d0d-5faa5f7f8fb1",
                plant_name="Plant S",
                type=PlantType.FIT,
            ),
        ]

    async def get_all_plants(self) -> List[Plant]:
        """Get all available plants"""
        # TODO: implement database query
        return self._dummy_plants

    async def search_plants(self, search_term: str = "") -> List[Plant]:
        """Search plants by name"""
        if not search_term:
            return await self.get_all_plants()

        # Filter plants by search term (case-insensitive)
        search_term_lower = search_term.lower()
        filtered_plants = [
            plant
            for plant in self._dummy_plants
            if search_term_lower in plant.plant_name.lower()
        ]

        return filtered_plants

    async def get_plant_by_id(self, plant_id: str) -> Optional[Plant]:
        """Get a specific plant by ID"""
        for plant in self._dummy_plants:
            if plant.plant_id == plant_id:
                return plant
        return None

    async def get_plants_by_type(self, plant_type: PlantType) -> List[Plant]:
        """Get plants filtered by type"""
        return [plant for plant in self._dummy_plants if plant.type == plant_type]

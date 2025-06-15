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
                plant_id="plant-001", plant_name="Solar Farm Alpha", type=PlantType.FIT
            ),
            Plant(
                plant_id="plant-002",
                plant_name="Residential Complex Beta",
                type=PlantType.ZERO_EXPORT,
            ),
            Plant(
                plant_id="plant-003",
                plant_name="Commercial Building Gamma",
                type=PlantType.FIT,
            ),
            Plant(
                plant_id="plant-004",
                plant_name="Industrial Park Delta",
                type=PlantType.ZERO_EXPORT,
            ),
            Plant(
                plant_id="plant-005",
                plant_name="School Campus Epsilon",
                type=PlantType.FIT,
            ),
            Plant(
                plant_id="plant-006",
                plant_name="Hospital Complex Zeta",
                type=PlantType.ZERO_EXPORT,
            ),
            Plant(
                plant_id="plant-007", plant_name="Shopping Mall Eta", type=PlantType.FIT
            ),
            Plant(
                plant_id="plant-008",
                plant_name="Office Tower Theta",
                type=PlantType.ZERO_EXPORT,
            ),
            Plant(
                plant_id="plant-009",
                plant_name="University Campus Iota",
                type=PlantType.FIT,
            ),
            Plant(
                plant_id="plant-010",
                plant_name="Manufacturing Plant Kappa",
                type=PlantType.ZERO_EXPORT,
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

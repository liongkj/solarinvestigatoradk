"""Plant Management API Controllers for Solar Investigator ADK"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
import logging

from adk.models.plant import Plant, PlantListResponse, PlantType
from adk.services.plant_service import PlantService

logger = logging.getLogger(__name__)

# Router for plant management endpoints
router = APIRouter(prefix="/api/plants", tags=["plant-management"])


@router.get("/", response_model=PlantListResponse)
async def list_plants(
    search: Optional[str] = Query(None, description="Search term for plant names"),
    plant_type: Optional[PlantType] = Query(None, description="Filter by plant type"),
    plant_service: PlantService = Depends(PlantService),
):
    """
    List all plants with optional search and filtering.

    Returns a list of all solar plants, optionally filtered by search term or type.
    """
    try:
        if plant_type:
            plants = await plant_service.get_plants_by_type(plant_type)
        elif search:
            plants = await plant_service.search_plants(search)
        else:
            plants = await plant_service.get_all_plants()

        return PlantListResponse(plants=plants, total=len(plants))

    except Exception as e:
        logger.error(f"Error listing plants: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{plant_id}", response_model=Plant)
async def get_plant(
    plant_id: str,
    plant_service: PlantService = Depends(PlantService),
):
    """
    Get a specific plant by ID.

    Returns detailed information about a specific solar plant.
    """
    try:
        plant = await plant_service.get_plant_by_id(plant_id)

        if not plant:
            raise HTTPException(status_code=404, detail="Plant not found")

        return plant

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plant {plant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search/{search_term}", response_model=PlantListResponse)
async def search_plants(
    search_term: str,
    plant_service: PlantService = Depends(PlantService),
):
    """
    Search plants by name.

    Returns a list of plants matching the search term.
    """
    try:
        plants = await plant_service.search_plants(search_term)
        return PlantListResponse(plants=plants, total=len(plants))

    except Exception as e:
        logger.error(f"Error searching plants with term '{search_term}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

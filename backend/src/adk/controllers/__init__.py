"""Controllers module for Solar Investigator ADK"""

from .investigation_management_controller_simplified import (
    router as investigation_management_router,
)

__all__ = ["investigation_management_router"]

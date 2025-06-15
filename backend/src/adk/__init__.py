"""
Solar Investigator ADK Backend

A FastAPI backend powered by Google's Agent Development Kit (ADK) for
solar project investigation and analysis.
"""

__version__ = "0.1.0"
__author__ = "Solar Investigator Team"

# Import only what's currently available to avoid import errors
try:
    from .config import settings

    __all__ = ["settings"]
except ImportError:
    __all__ = []

# TODO: Add imports as modules are implemented
# from .models import *
# from .agents import *
# from .tools import *
# from .services import *

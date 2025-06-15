"""ADK Services configuration using DatabaseSessionService."""

import logging
from typing import Optional

from google.adk.core import BaseSessionService
from google.adk.core.db import DatabaseSessionService
from google.adk.core.memory import BaseMemoryService, InMemoryMemoryService
from google.adk.core.artifact import BaseArtifactService, InMemoryArtifactService
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ..config.settings import settings

logger = logging.getLogger(__name__)

# SQLAlchemy base for ADK database models
Base = declarative_base()


class ADKServices:
    """Container for ADK services with DatabaseSessionService."""

    def __init__(self):
        self._session_service: Optional[BaseSessionService] = None
        self._memory_service: Optional[BaseMemoryService] = None
        self._artifact_service: Optional[BaseArtifactService] = None
        self._db_engine = None
        self._db_session_factory = None

    def initialize(self):
        """Initialize all ADK services."""
        logger.info("Initializing ADK services...")

        # Initialize database engine
        self._setup_database()

        # Initialize services
        self._session_service = self._create_session_service()
        self._memory_service = self._create_memory_service()
        self._artifact_service = self._create_artifact_service()

        logger.info("ADK services initialized successfully")

    def _setup_database(self):
        """Set up database connection for ADK."""
        try:
            # Create SQLAlchemy engine
            self._db_engine = create_engine(
                settings.database_url,
                echo=settings.database_echo,
                pool_pre_ping=True,
                pool_recycle=300,
            )

            # Create session factory
            self._db_session_factory = sessionmaker(
                autocommit=False, autoflush=False, bind=self._db_engine
            )

            # Create tables if they don't exist
            Base.metadata.create_all(bind=self._db_engine)

            logger.info(f"Database connection established: {settings.database_url}")

        except Exception as e:
            logger.error(f"Failed to setup database: {e}")
            raise

    def _create_session_service(self) -> BaseSessionService:
        """Create DatabaseSessionService for persistent session storage."""
        try:
            # Use DatabaseSessionService with PostgreSQL
            session_service = DatabaseSessionService(
                connection_string=settings.database_url,
                table_name="adk_sessions",
                schema_name="public",
            )

            logger.info("DatabaseSessionService created successfully")
            return session_service

        except Exception as e:
            logger.error(f"Failed to create session service: {e}")
            # Fallback to in-memory service for development
            logger.warning("Falling back to InMemorySessionService")
            from google.adk.core.session import InMemorySessionService

            return InMemorySessionService()

    def _create_memory_service(self) -> BaseMemoryService:
        """Create memory service for long-term context storage."""
        try:
            # For now, use in-memory service
            # In production, you might want to use a database-backed memory service
            memory_service = InMemoryMemoryService(
                max_tokens=settings.memory_max_tokens
            )

            logger.info("Memory service created successfully")
            return memory_service

        except Exception as e:
            logger.error(f"Failed to create memory service: {e}")
            return InMemoryMemoryService()

    def _create_artifact_service(self) -> BaseArtifactService:
        """Create artifact service for storing investigation files."""
        try:
            # For now, use in-memory service
            # In production, you might want to use GCS or S3
            artifact_service = InMemoryArtifactService()

            logger.info("Artifact service created successfully")
            return artifact_service

        except Exception as e:
            logger.error(f"Failed to create artifact service: {e}")
            return InMemoryArtifactService()

    @property
    def session_service(self) -> BaseSessionService:
        """Get session service."""
        if self._session_service is None:
            raise RuntimeError("Services not initialized. Call initialize() first.")
        return self._session_service

    @property
    def memory_service(self) -> BaseMemoryService:
        """Get memory service."""
        if self._memory_service is None:
            raise RuntimeError("Services not initialized. Call initialize() first.")
        return self._memory_service

    @property
    def artifact_service(self) -> BaseArtifactService:
        """Get artifact service."""
        if self._artifact_service is None:
            raise RuntimeError("Services not initialized. Call initialize() first.")
        return self._artifact_service

    def close(self):
        """Clean up services and connections."""
        logger.info("Closing ADK services...")

        if self._db_engine:
            self._db_engine.dispose()

        logger.info("ADK services closed")


# Global ADK services instance
adk_services = ADKServices()


def get_adk_services() -> ADKServices:
    """Get global ADK services instance."""
    return adk_services

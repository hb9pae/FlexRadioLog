"""FastAPI application factory and lifecycle management."""

from contextlib import asynccontextmanager
import logging
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from flexradiolog.api.routes import router
from flexradiolog.config import AppConfig
from flexradiolog.db.database import Database
from flexradiolog.radio.client import RadioClient
from flexradiolog.radio.tracker import RadioStateTracker

logger = logging.getLogger(__name__)


def create_app(config: Optional[AppConfig] = None, start_radio_client: bool = True) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = AppConfig.load_from_yaml()

    db = Database(config.database)
    tracker = RadioStateTracker(db)
    radio_client = RadioClient(config.radio, tracker)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        logger.info("Initializing FlexRadioLog database...")
        await db.init_models()
        await db.seed_initial_allocations(config.initial_allocations)
        await db.close_abandoned_sessions()
        await tracker.reload_ip_cache()

        if start_radio_client:
            logger.info("Starting FlexRadio connection client...")
            await radio_client.start()

        yield

        # Shutdown
        if start_radio_client:
            logger.info("Stopping FlexRadio connection client...")
            await radio_client.stop()

        await db.close()
        logger.info("FlexRadioLog shutdown complete.")

    app = FastAPI(
        title=config.api.title,
        version="0.1.0",
        description="REST API for monitoring FlexRadio 6400 user sessions, PTT events, and statistics.",
        lifespan=lifespan,
    )

    # Allow CORS for external dashboards and visualization clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach shared components to app state
    app.state.config = config
    app.state.db = db
    app.state.tracker = tracker
    app.state.radio_client = radio_client

    app.include_router(router)

    return app

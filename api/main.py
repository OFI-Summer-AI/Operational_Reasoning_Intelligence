"""FastAPI app factory — Railway-deployable."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import RequestLoggingMiddleware
from api.routes import health, incidents
from config.settings import get_settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from layers.memory.vector_store import IncidentVectorStore

        store = IncidentVectorStore(
            persist_dir=settings.chromadb_persist_dir,
            collection_name=settings.chromadb_collection_name,
        )
        count = store.count()
        logger.info("api.startup", chromadb_count=count, model=settings.groq_model)
        if count == 0:
            logger.warning("api.startup.empty_db", hint="Run: python main.py --mode seed")
        yield

    app = FastAPI(
        title="ORI API",
        description="Operational Reasoning Intelligence Platform — RCA as a Service",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(incidents.router)

    return app


app = create_app()

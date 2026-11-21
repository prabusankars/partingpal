import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, SessionLocal
from .interview.prompt_config import get_prompt_config
from .routers import admin, interview

settings = get_settings()
# Transcripts are never logged: only ids and error messages.
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("partingpal")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Creates missing tables; switch to Alembic migrations once the schema starts changing.
    Base.metadata.create_all(SessionLocal.kw["bind"])
    prompts = get_prompt_config()
    log.info("Prompts version %s loaded (%d topics)", prompts.version, len(prompts.topics))
    if settings.auth_disabled:
        log.warning("AUTH_DISABLED is set: the HR dashboard is open to anyone. Use only for local development.")
    elif not (settings.allowed_emails or settings.allowed_domains):
        log.warning("No ADMIN_ALLOWED_EMAILS / ADMIN_ALLOWED_DOMAINS configured: nobody can sign in to the dashboard.")
    yield


app = FastAPI(title="Parting Pal API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "X-Auth-Token", "Content-Type"],
)
app.include_router(admin.router)
app.include_router(interview.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

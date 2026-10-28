"""FastAPI entry point."""

from fastapi import FastAPI

from app.schema import SCHEMA_VERSION

app = FastAPI(title="OAuth Setup Guides", version="0.1.0")


@app.get("/api/health")
@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "schema_version": SCHEMA_VERSION}

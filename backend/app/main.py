"""FastAPI entry point."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.markdown import render_markdown
from app.schema import SCHEMA_VERSION, Guide
from app.store import GuideStore, GuideSummary, guides_dir

app = FastAPI(title="OAuth Setup Guides", version="0.1.0")


@lru_cache(maxsize=1)
def get_store() -> GuideStore:
    return GuideStore.from_directory(guides_dir())


Store = Annotated[GuideStore, Depends(get_store)]


@app.get("/api/health")
@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "schema_version": SCHEMA_VERSION}


@app.get("/api/guides")
def list_guides(store: Store) -> list[GuideSummary]:
    return store.summaries()


def _find(slug: str, store: GuideStore) -> Guide:
    guide = store.get(slug)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"No guide found for '{slug}'.")
    return guide


@app.get("/api/guides/{slug}")
def get_guide(slug: str, store: Store) -> Guide:
    return _find(slug, store)


@app.get("/api/guides/{slug}/markdown", response_class=PlainTextResponse)
def get_guide_markdown(slug: str, request: Request, store: Store) -> PlainTextResponse:
    guide = _find(slug, store)
    share_url = str(request.base_url).rstrip("/") + f"/guides/{slug}"
    return PlainTextResponse(
        render_markdown(guide, share_url=share_url), media_type="text/markdown; charset=utf-8"
    )

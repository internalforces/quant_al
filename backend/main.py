from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.routers.analysis import router

app = FastAPI(title="MB Quant API")
project_root = Path(__file__).resolve().parent.parent
frontend_dist = project_root / "frontend" / "dist"
frontend_index = frontend_dist / "index.html"
frontend_dist_resolved = frontend_dist.resolve()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def _resolve_frontend_path(path: str) -> Optional[Path]:
    candidate = (frontend_dist / path).resolve()
    try:
        candidate.relative_to(frontend_dist_resolved)
    except ValueError:
        return None
    return candidate


if frontend_index.exists():
    @app.get("/", include_in_schema=False)
    async def serve_frontend_index():
        return FileResponse(frontend_index)


    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_app(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")

        candidate = _resolve_frontend_path(full_path)
        if candidate and candidate.is_file():
            return FileResponse(candidate)

        if Path(full_path).suffix:
            raise HTTPException(status_code=404, detail="Static asset not found")

        return FileResponse(frontend_index)

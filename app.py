import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ui.web_app import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("netryx")

app = FastAPI(title="Netryx Nova", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=Path(__file__).parent / "ui" / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "ui" / "static"), name="static")

app.include_router(router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    from config import HOST, PORT

    uvicorn.run("app:app", host=HOST, port=PORT, reload=True)

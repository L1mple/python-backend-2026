from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .routes import router
from .websocket import router as websocket_router


app = FastAPI(title="Shop API")

Instrumentator().instrument(app).expose(app)

app.include_router(router)
app.include_router(websocket_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

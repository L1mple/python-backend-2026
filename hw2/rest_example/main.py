from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from hw2.rest_example.api.pokemon import router

app = FastAPI(title="Pokemon REST API Example")

app.include_router(router)
Instrumentator().instrument(app).expose(app)

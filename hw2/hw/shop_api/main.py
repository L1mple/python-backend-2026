from fastapi import FastAPI
from .routes import router2

app = FastAPI(title="Shop API")
app.include_router(router2)

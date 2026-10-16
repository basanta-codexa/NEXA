from fastapi import FastAPI, Depends
from routers.agents import router as agents_router
from routers.tenants import router as tenants_router
from routers.users import router as users_router
from routers.documents import router as documents_router
from routers.voice import router as voice_router

app = FastAPI()


@app.get("/")
def read_root():

    return {"message": "Welcome to NEXA"}


@app.get("/hello")
def hello():
    return {
        "message": "Hello from NEXA AI"
    }


app.include_router(agents_router)
app.include_router(tenants_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(voice_router)
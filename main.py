from fastapi import FastAPI, Depends
from routers.agents import router as agents_router
from routers.tenants import router as tenants_router

from dependencies.tenant import get_current_tenant_id
from routers.users import router as users_router

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
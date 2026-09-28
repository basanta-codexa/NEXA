from pydantic import BaseModel


class CreateAgent(BaseModel):
    name: str
    role: str
    language: str

class UpdateAgent(BaseModel):
    name: str
    role: str
    language: str

class CreateTenant(BaseModel):
    name: str
    description: str

class CreateUser(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str
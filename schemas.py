from pydantic import BaseModel


# Define Pydantic models for request and response
class User(BaseModel):
    login: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class Rate(BaseModel):
    rate_name: str
    rate_speed: str
    rate_cost: str


class UserData(BaseModel):
    username: str
    account: str
    balance: float
    rate: Rate

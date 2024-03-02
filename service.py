import os

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

from db.billing_db import get_user
from dotenv import load_dotenv

load_dotenv()

# Define some constants for JWT
SECRET_KEY = os.getenv('secret')  # Change this to a secure secret key
ALGORITHM = os.getenv('algorithm')
ACCESS_TOKEN_EXPIRE_MINUTES = 10
REFRESH_TOKEN_EXPIRE_YEARS = 1

# Define a security scheme for bearer tokens
bearer_scheme = HTTPBearer()

# Create a password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Example user data (replace this with your actual user database)
fake_users_db = {
    "user": {
        "username": "user",
        "password": "123456",  # hashed "password"
    }
}


# Function to create access token
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Function to create refresh token
def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_YEARS * 365)
    # expire = datetime.utcnow() + timedelta(minutes=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Function to verify password
def verify_password(plain_password, db_password):
    # return pwd_context.verify(plain_password, db_password)
    return plain_password == db_password


# Function to authenticate user
async def authenticate_user(login: str, password: str):
    # user = fake_users_db.get(login)
    user = await get_user(login)
    if not user:
        return False
    if not verify_password(password, user["password"]):
        return False
    return user


# Dependency to get current user
# def get_current_user(token: str = Depends(create_access_token)):
#     credentials_exception = HTTPException(
#         status_code=401,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise credentials_exception
#         return username
#     except JWTError:
#         raise credentials_exception

# Function to get current user from access token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return payload.get("sub")


# Function to decode token
def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

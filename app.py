import datetime

from fastapi import FastAPI, HTTPException, Depends
from db.app_db import init_db, store_refresh_token, add_user, is_refresh_token_valid
from db.billing_db import get_user_data, get_balance, get_rate
from schemas import User, Token, RefreshTokenRequest, UserData
from service import authenticate_user, create_access_token, create_refresh_token, decode_token, get_current_user

# Define the FastAPI app
app = FastAPI()


# Define the authentication route
@app.post("/api/auth", response_model=Token)
async def login_for_access_token(user: User):
    authenticated_user = await authenticate_user(user.login, user.password)
    if not authenticated_user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(
        data={"sub": user.login})
    refresh_token = create_refresh_token(data={"sub": user.login})
    await add_user(user.login, user.password)
    await store_refresh_token(user.login, user.password, refresh_token)
    return {"access_token": access_token, "refresh_token": refresh_token}


# Define the refresh token route
@app.post("/api/refresh-token", response_model=Token)
async def refresh_token(request: RefreshTokenRequest):
    token_payload = decode_token(request.refresh_token)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Verify if the refresh token exists in the database
    is_valid = await is_refresh_token_valid(request.refresh_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Extract username from refresh token payload
    username = token_payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Generate a new access token
    access_token = create_access_token(data={"sub": username})

    # Return the new access token along with the same refresh token
    return {"access_token": access_token, "refresh_token": request.refresh_token}


# Define the /api/me endpoint
@app.get("/api/me", response_model=UserData)
async def read_current_user(current_user: str = Depends(get_current_user)):
    user_data = await get_user_data(current_user)
    balance = await get_balance(current_user)
    rate = await get_rate(current_user)
    # Here you can fetch additional information about the current user from your database
    return {"username": user_data['fio'], "account": current_user, "balance": balance, "rate": rate}


@app.on_event("startup")
async def startup_event():
    await init_db()

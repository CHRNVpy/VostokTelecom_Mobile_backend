import datetime

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from db.app_db import init_db, store_refresh_token, add_user, is_refresh_token_valid
from db.billing_db import get_user_data, get_payments, update_password
from schemas import User, Token, RefreshTokenRequest, UserData, PaymentsList, PasswordUpdate, News
from service import authenticate_user, create_access_token, create_refresh_token, decode_token, get_current_user, \
    validate_password

# Define the FastAPI app
app = FastAPI(title='VostokTelekom Mobile API', description='BASE URL >> https://mobile.vt54.ru')


# Define the authentication route
@app.post("/api/auth", response_model=Token, responses={401: {"description": "Incorrect username or password"}})
async def login_for_access_token(user: User):
    authenticated_user = await authenticate_user(user.login, user.password)
    if not authenticated_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = create_access_token(
        data={"sub": user.login})
    refresh_token = create_refresh_token(data={"sub": user.login})
    await add_user(user.login, user.password)
    await store_refresh_token(user.login, user.password, refresh_token)
    return {"access_token": access_token, "refresh_token": refresh_token}


# Define the refresh token route
@app.post("/api/refresh-token", response_model=Token, responses={401: {"description": "Invalid refresh token"}})
async def refresh_token(request: RefreshTokenRequest):
    token_payload = decode_token(request.refresh_token)
    if not token_payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Verify if the refresh token exists in the database
    is_valid = await is_refresh_token_valid(request.refresh_token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Extract username from refresh token payload
    username = token_payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Generate a new access token
    access_token = create_access_token(data={"sub": username})

    # Return the new access token along with the same refresh token
    return {"access_token": access_token, "refresh_token": request.refresh_token}


# Define the /api/me endpoint
@app.get("/api/me", response_model=UserData, responses={401: {"description": "Invalid access token"}})
async def read_current_user(current_user: str = Depends(get_current_user)):
    user_data = await get_user_data(current_user)
    # Here you can fetch additional information about the current user from your database
    return {"username": user_data['full_name'],
            "account": current_user,
            "balance": user_data['balance'],
            "rate": {"rate_name": user_data["rate_name"],
                     "rate_speed": user_data["rate_speed"],
                     "rate_cost": user_data["rate_cost"]},
            "min_pay": user_data["min_pay"],
            "pay_day": user_data["pay_day"]}


@app.patch("/api/me", responses={401: {"description": "Invalid access token"},
                                 400: {"description": "Password cannot be empty"}})
async def set_new_password(password: PasswordUpdate = Depends(validate_password),
                           current_user: str = Depends(get_current_user)):
    await update_password(current_user, password.password)


@app.get("/api/collection-payments", response_model=PaymentsList,
         responses={401: {"description": "Invalid access token"}})
async def get_payments_history(current_user: str = Depends(get_current_user)):
    payments_history = await get_payments(current_user)
    return {'payments': payments_history}


@app.get("/api/collection-news", response_model=News,
         responses={401: {"description": "Invalid access token"}})
async def get_news(current_user: str = Depends(get_current_user)):
    user = current_user
    news = [{'article': 'Восток-Телеком объявляет о запуске новой программы лояльности для своих клиентов'},
            {'article': 'Новый тарифный план, который призван удовлетворить потребности самых требовательных клиентов'}
            ]
    return {'news': news}


@app.on_event("startup")
async def startup_event():
    await init_db()

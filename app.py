import datetime
import json
import uuid

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from acquiring import pay_request, delete_bindings
from db.app_db import init_db, store_refresh_token, add_user, is_refresh_token_valid, get_autopay, delete_autopay
from db.billing_db import get_user_data, get_payments, update_password
from schemas import User, Token, RefreshTokenRequest, UserData, HistoryPaymentsList, PasswordUpdate, News, Payment, \
    PaymentAmount, AutoPayDetails, Accident
from service import authenticate_user, create_access_token, create_refresh_token, decode_token, get_current_user, \
    validate_password
from tasks import check_payment_status, get_alert

# Define the FastAPI app
app = FastAPI(title='VostokTelekom Mobile API', description='BASE URL >> https://mobile.vt54.ru')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


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


@app.get("/api/collection-payments", response_model=HistoryPaymentsList,
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


@app.post("/api/pay", response_model=Payment,
          responses={401: {"description": "Invalid access token"}})
async def pay_handler(request: PaymentAmount,
                      background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    order = str(uuid.uuid4())
    response = await pay_request(request.amount_roubles, order)
    json_response = json.loads(response)
    background_tasks.add_task(check_payment_status, json_response['orderId'], current_user, autopay=False)
    return json_response


@app.get("/api/autopay", response_model=AutoPayDetails,
         responses={401: {"description": "Invalid access token"}})
async def get_autopay_data(current_user: str = Depends(get_current_user)):
    data = await get_autopay(current_user)
    return data


@app.post("/api/autopay", response_model=Payment,
          responses={401: {"description": "Invalid access token"}})
async def enable_autopay(request: PaymentAmount,
                         background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    order = str(uuid.uuid4())
    response = await pay_request(request.amount_roubles, order, auto_payment=True, client_id=current_user)
    json_response = json.loads(response)
    background_tasks.add_task(check_payment_status, json_response['orderId'], current_user, autopay=True)
    return json_response


@app.patch("/api/autopay", response_model=AutoPayDetails,
           responses={401: {"description": "Invalid access token"}})
async def disable_autopay(current_user: str = Depends(get_current_user)):
    await delete_bindings(current_user)
    await delete_autopay(current_user)
    return {'enabled': False, 'pay_day': '', 'pay_summ': 0.0}


@app.get("/api/accident", response_model=Accident,
         responses={401: {"description": "Invalid access token"}})
async def get_accident(current_user: str = Depends(get_current_user)):
    alert_status = await get_alert(current_user)
    return alert_status



@app.on_event("startup")
async def startup_event():
    await init_db()

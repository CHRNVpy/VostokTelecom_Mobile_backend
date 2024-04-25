import datetime
import json
import uuid
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from acquiring import pay_request, delete_bindings
from db.app_db import init_db, store_refresh_token, add_user, is_refresh_token_valid, get_autopay, delete_autopay, \
    get_accident_status, add_message, get_messages, get_rooms, get_group_news
from db.billing_db import get_user_data, get_payments, update_password
from schemas import User, Token, RefreshTokenRequest, UserData, HistoryPaymentsList, PasswordUpdate, News, Payment, \
    PaymentAmount, AutoPayDetails, Accident, MessagesList, Message, Rooms, NewAdminMessage
from service import authenticate_user, create_access_token, create_refresh_token, decode_token, get_current_user, \
    validate_password, is_support
from tasks import check_payment_status, check_alerts, init_autopay

app = FastAPI(title='VostokTelekom Mobile API', description='BASE URL >> https://mobile.vt54.ru')
scheduler = AsyncIOScheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# Define the authentication route
@app.post("/api/auth", response_model=Token, responses={401: {"description": "Incorrect username or password"}},
          tags=['auth'])
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
@app.post("/api/refresh-token", response_model=Token, responses={401: {"description": "Invalid refresh token"}},
          tags=['auth'])
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
@app.get("/api/me", response_model=UserData, responses={401: {"description": "Invalid access token"}},
         tags=['user'])
async def read_current_user(current_user: str = Depends(get_current_user)):
    user_data = await get_user_data(current_user)
    return user_data


@app.patch("/api/me", responses={401: {"description": "Invalid access token"},
                                 400: {"description": "Password cannot be empty"}}, tags=['user'])
async def set_new_password(password: PasswordUpdate = Depends(validate_password),
                           current_user: str = Depends(get_current_user)):
    await update_password(current_user, password.password)


@app.get("/api/collection-payments", response_model=HistoryPaymentsList,
         responses={401: {"description": "Invalid access token"}}, tags=['collection'])
async def get_payments_history(current_user: str = Depends(get_current_user)):
    payments_history = await get_payments(current_user)
    return {'payments': payments_history}


@app.get("/api/collection-news", response_model=News,
         responses={401: {"description": "Invalid access token"}}, tags=['collection'])
async def get_news(current_user: str = Depends(get_current_user)):
    news = await get_group_news(current_user)
    return news


@app.post("/api/pay", response_model=Payment,
          responses={401: {"description": "Invalid access token"}}, tags=['payments'])
async def process_payment(request: PaymentAmount,
                          background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    response = await pay_request(request.amount_roubles)
    background_tasks.add_task(check_payment_status, response['orderId'], current_user, autopay=False)
    return response


@app.get("/api/autopay", response_model=AutoPayDetails,
         responses={401: {"description": "Invalid access token"}}, tags=['payments'])
async def get_autopay_data(current_user: str = Depends(get_current_user)):
    data = await get_autopay(current_user)
    return data


@app.post("/api/autopay", response_model=Payment,
          responses={401: {"description": "Invalid access token"}}, tags=['payments'])
async def enable_autopay(request: PaymentAmount,
                         background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    response = await pay_request(request.amount_roubles, auto_payment=True, client_id=current_user)
    background_tasks.add_task(check_payment_status, response['orderId'], current_user, autopay=True)
    return response


@app.patch("/api/autopay", response_model=AutoPayDetails,
           responses={401: {"description": "Invalid access token"}}, tags=['payments'])
async def disable_autopay(current_user: str = Depends(get_current_user)):
    await delete_bindings(current_user)
    await delete_autopay(current_user)
    return {'enabled': False, 'pay_day': '', 'pay_summ': 0.0}


@app.get("/api/accident", response_model=Accident,
         responses={401: {"description": "Invalid access token"}, 500: {"description": "Internal server error"}},
         tags=['accident'])
async def get_accident(current_user: str = Depends(get_current_user)):
    alert_status = await get_accident_status(current_user)
    return {"accident": alert_status}


@app.get("/api/chat", response_model=MessagesList,
         responses={401: {"description": "Invalid access token"}, 500: {"description": "Internal server error"}},
         tags=['chat'])
async def get_chat_messages(current_user: str = Depends(get_current_user),
                            from_id: Optional[int] = Query(None, description='filters results from id (optional)')):
    # to_id: Optional[int] = Query(None, description='filters results to id (optional)')):
    messages = await get_messages(room_id=current_user, from_id=from_id)
    return messages


@app.post("/api/chat", response_model=MessagesList,
          responses={401: {"description": "Invalid access token"}, 500: {"description": "Internal server error"}},
          tags=['chat'])
async def post_new_user_message(message: Message, current_user: str = Depends(get_current_user)):
    if message.message:
        await add_message(current_user, message.role, message.message)
    messages = await get_messages(room_id=current_user, from_id=message.id)
    return messages


@app.get('/api/rooms', response_model=Rooms,
         responses={401: {"description": "Invalid access token"}, 500: {"description": "Internal server error"}},
         tags=['rooms'])
async def get_chat_rooms(current_user: str = Depends(get_current_user)):
    if not is_support(current_user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect admin credentials")
    rooms = await get_rooms()
    return rooms


@app.get('/api/rooms/chat', response_model=MessagesList,
         responses={401: {"description": "Invalid access token"}, 500: {"description": "Internal server error"}},
         tags=['rooms'])
async def get_rooms_messages(room_id: Optional[str] = Query(None, description='room_id'),
                             from_id: Optional[int] = Query(None, description='filters results from id (optional)'),
                             current_user: str = Depends(get_current_user)):
    if not is_support(current_user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect admin credentials")
    messages = await get_messages(room_id=room_id, from_id=from_id)
    return messages


@app.post('/api/rooms/chat', response_model=MessagesList,
          responses={401: {"description": "Invalid access token"}, 500: {"description": "Internal server error"}},
          tags=['rooms'])
async def post_new_admin_message(message: NewAdminMessage,
                                 current_user: str = Depends(get_current_user)):
    if not is_support(current_user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect admin credentials")
    if message.message:
        await add_message(message.room_id, message.role, message.message)
    messages = await get_messages(room_id=message.room_id, from_id=message.from_id)
    return messages


@app.on_event("startup")
async def startup_event():
    await init_db()
    scheduler.start()
    scheduler.add_job(check_alerts, trigger='interval', hours=1, max_instances=1)
    scheduler.add_job(init_autopay, trigger='interval', days=1, max_instances=1)


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.remove_all_jobs()
    scheduler.shutdown()

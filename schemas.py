from typing import List, Optional

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
    role: str
    account: str
    balance: float
    rate: Rate
    min_pay: float
    pay_day: str


class PasswordUpdate(BaseModel):
    password: str


class HistoryPayment(BaseModel):
    id: int
    date: str
    summ: int


class HistoryPaymentsList(BaseModel):
    payments: List[HistoryPayment]


class NewsArticle(BaseModel):
    article: str


class News(BaseModel):
    news: List[NewsArticle]


class Payment(BaseModel):
    orderId: str
    formUrl: str


class PaymentAmount(BaseModel):
    amount_roubles: int


class AutoPayDetails(BaseModel):
    enabled: bool
    pay_day: str
    pay_summ: float


class Accident(BaseModel):
    accident: bool


class Director(BaseModel):
    name: str
    inn: str


class Classifiers(BaseModel):
    okpo: str
    okato: str
    oktmo: str
    okogu: str
    okfs: str
    okopf: str
    okved: str


class Company(BaseModel):
    fullName: str
    shortName: str
    legalAddress: str
    postalAddress: str
    phone: Optional[str] = None
    inn: str
    kpp: str
    ogrn: str
    bankAccount: str
    correspondentAccount: str
    bankBik: str
    bank: str
    classifiers: Classifiers
    director: Director
    email: str


class Message(BaseModel):
    id: int = 0
    role: str = 'user'
    message: str
    type: Optional[str] = None
    created: Optional[int] = None


class SupportMessage(BaseModel):
    id: int = None
    room_id: str
    role: str = 'support'
    message: str


class MessagesList(BaseModel):
    messages: List[Message]


class Room(BaseModel):
    name: str
    latest_message: Message


class Rooms(BaseModel):
    rooms: List[Room]

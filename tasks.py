import asyncio
import json
import time

from acquiring import get_status_payment
from db.app_db import set_autopay


async def check_payment_status(order_id, user_id=None):
    while True:
        status = await get_status_payment(order_id)
        if json.loads(status).get('OrderStatus'):
            if json.loads(status)['OrderStatus'] == 2:
                # print('Проведена полная авторизация суммы заказа')
                if user_id is not None:
                    await set_autopay(user_id, json.loads(status)['bindingId'])
                break
            elif json.loads(status)['OrderStatus'] in [3, 6]:
                # print('Авторизация отклонена')
                break
            else:
                # print(json.loads(status)['OrderStatus'])
                await asyncio.sleep(5)

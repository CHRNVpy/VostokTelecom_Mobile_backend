import asyncio
import datetime
import json
import time

import aiohttp

from acquiring import get_status_payment
from db.app_db import set_autopay
from db.billing_db import update_user_balance_old


async def check_payment_status(order_id: str, user_id=None, autopay=False) -> None:
    while True:
        json_status = await get_status_payment(order_id)
        status = json.loads(json_status)
        print(status)
        if status.get('OrderStatus'):
            if status['OrderStatus'] == 2:
                # print('Проведена полная авторизация суммы заказа')
                if autopay:
                    await set_autopay(user_id, status['bindingId'])
                payment_summ = int(status['Amount']) / 100
                txn_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                update_balance_url = (f'https://billing-2.vt54.ru/alfa-pay/1?command=pay&txn_id={order_id}&'
                                      f'txn_date={txn_date}&sum={float(payment_summ)}&account={user_id}')
                match len(user_id):
                    case 4:
                        await update_user_balance_old(user_id, payment_summ, order_id)
                    case 5:
                        async with aiohttp.ClientSession() as session:
                            await session.get(update_balance_url)
                break
            elif status['OrderStatus'] in [3, 6]:
                # print('Авторизация отклонена')
                break
            else:
                # print(json.loads(status)['OrderStatus'])
                await asyncio.sleep(5)


async def zabbix():
    url = 'https://zabbix2.vt54.ru/zabbix/api_jsonrpc.php'
    data = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "filter": {
                "host": [
                    "Zabbix server",
                    "Linux server"
                ]
            }
        },
        "auth": "09987a96ea1812b88d3bd447953425eca86421838db076b236b03333ddb27b73",
        "id": 1
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, json=data) as response:
            response_json = await response.json()
            print(response_json)


# asyncio.run(zabbix())

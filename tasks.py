import asyncio
import datetime
import json
import os
import time

import aiohttp

from acquiring import get_status_payment
from db.app_db import set_autopay
from db.billing_db import update_user_balance_old, get_user_group_id
from dotenv import load_dotenv

load_dotenv()


async def check_payment_status(order_id: str, user_id=None, autopay=False) -> None:
    while True:
        json_status = await get_status_payment(order_id)
        status = json.loads(json_status)
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
                            response = await session.get(update_balance_url)
                            print(await response.text())
                break
            elif status['OrderStatus'] in [3, 6]:
                # print('Авторизация отклонена')
                break
            else:
                # print(json.loads(status)['OrderStatus'])
                await asyncio.sleep(5)


async def get_alert(account: str):
    user_group_id = await get_user_group_id(account)
    url = 'https://zabbix2.vt54.ru/zabbix/api_jsonrpc.php'
    host_group_data = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "output": ["groupid", "name"],
            "filter": {
                "name": [
                    f"felix-abons-{user_group_id}",
                ]
            }
        },
        "auth": os.getenv('zabbix_token'),
        "id": 2
    }

    async def zabbix_request(url, data):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, json=data) as response:
                response_json = await response.json()
                return response_json

    group_id_response = await zabbix_request(url, host_group_data)
    group_id = group_id_response['result'][0]['groupid'] if group_id_response['result'] else 0

    status_data = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["name", "status"],
            "groupids": [int(group_id)]
        },
        "auth": os.getenv('zabbix_token'),
        "id": 1
    }

    status_response = await zabbix_request(url, status_data)
    statuses = [int(status['status']) for status in status_response['result']]
    if 1 in statuses:
        return {"accident": True}
    else:
        return {"accident": False}


# print(asyncio.run(get_alert('1104')))

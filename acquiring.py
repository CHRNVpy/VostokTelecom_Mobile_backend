import asyncio
import json
import os
import time
import uuid

import aiohttp
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv('BANK_USER')
PASSWORD = os.getenv('BANK_PASS')


async def pay_request(amount_rubles, auto_payment=False, client_id=None):
    order_number = str(uuid.uuid4())
    amount_kopecks = amount_rubles * 100
    url = 'https://pay.alfabank.ru/payment/rest/register.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'orderNumber': order_number,
        'amount': amount_kopecks,
        'returnUrl': 'https://mobile.vt54.ru/top-up/done',
        'failUrl': 'https://mobile.vt54.ru/top-up/fail',
        'pageView': 'MOBILE',
        'description': client_id
    }

    if auto_payment:
        params['clientId'] = client_id

    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            print(await response.text())
            return json.loads(await response.text())


async def autopay_request(order_id, binding_id, client_ip):
    url = 'https://pay.alfabank.ru/payment/rest/paymentOrderBinding.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'mdOrder': order_id,
        'bindingId': binding_id,
        'ip': client_ip,
        'tii': 'U',
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            print(response.url)
            print(await response.text())
            return await response.text()


async def get_status_payment(order_id):
    url = 'https://pay.alfabank.ru/payment/rest/getOrderStatus.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'orderId': order_id
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            # print(response.url)
            # print(await response.text())
            return await response.text()


async def get_bindings(client_id):
    url = 'https://pay.alfabank.ru/payment/rest/getBindings.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'clientId': client_id
    }
    headers = {'accept': '*/*'}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, headers=headers) as response:
            result = await response.text()
            return json.loads(result)


async def delete_binding(session, binding_id):
    url = 'https://pay.alfabank.ru/payment/rest/unBindCard.do'
    params = {
        'userName': USER,
        'password': PASSWORD,
        'bindingId': binding_id
    }
    headers = {'accept': '*/*'}

    async with session.post(url, params=params, headers=headers) as response:
        print(await response.text())


async def delete_bindings(client_id):
    bindings = await get_bindings(client_id)
    binding_ids = bindings['bindings']

    async with aiohttp.ClientSession() as session:
        tasks = [delete_binding(session, binding_id['bindingId']) for binding_id in binding_ids]
        await asyncio.gather(*tasks)

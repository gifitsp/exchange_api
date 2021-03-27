import time
import datetime
import requests
import hmac
import base64
import hashlib
import json
from urllib import parse
import urllib.parse
from requests import Session


class ContractClient(object):
    api_base = "https://api.gateio.ws"
    prefix = "/api/v4"

    def __del__(self):
        if self.session:
            self.session.close()

    def __init__(self, access_key="",  secret_key="", api_base="", **kwargs):
        self.session = Session()
        self.access_key = access_key
        self.secret_key = secret_key
        if api_base:
            self.api_base = api_base.rstrip('/')
        self.proxies = kwargs.get('proxies', {})

    def gen_sign(self, method, url, query_string=None, payload_string=None):
        key = self.access_key        # api_key
        secret = self.secret_key     # api_secret

        t = time.time()
        m = hashlib.sha512()
        m.update((payload_string or "").encode('utf-8'))
        hashed_payload = m.hexdigest()
        s = '%s\n%s\n%s\n%s\n%s' % (method, url, query_string or "", hashed_payload, t)
        sign = hmac.new(secret.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
        return {'KEY': key, 'Timestamp': str(t), 'SIGN': sign}

    def contract_reqeust(self, method, endpoint, payload, include_body, is_private):
        payload = {} if payload is None else payload
        p_str = urllib.parse.urlencode(sorted(payload.items()))
        url = f'{self.api_base}{endpoint}'
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        url = self.prefix + endpoint
        if len(payload) > 0:
            request_content = json.dumps(payload)
        else:
            request_content = ''
        if is_private:
            headers.update(self.gen_sign(method, url, "", request_content))
        if include_body:
            url = f'{url}?{p_str}' if p_str else url
        self.session.cookies.clear()
        resp = self.session.request(method, self.api_base + url, headers=headers, data=request_content, timeout=5, proxies=self.proxies)
        if resp.text != '':
            return resp.json()
        return {'code': resp.status_code, 'msg': resp.reason}

    def contract_get(self, endpoint, payload=None, include_body=True, is_private=False):
        return self.contract_reqeust('GET', endpoint, payload, include_body, is_private)

    def contract_post(self, endpoint, payload, include_body=True, is_private=False):
        return self.contract_reqeust('POST', endpoint, payload, include_body, is_private)

    def contract_delete(self, endpoint, payload, include_body=True, is_private=False):
        return self.contract_reqeust('DELETE', endpoint, payload, include_body, is_private)

    def get_contract_depth(self, position, settle, limit=5):
        _settle = settle.lower()
        endpoint = f'/futures/{_settle}/order_book'
        payload = {
            'contract': position + '_' + settle,
            'limit': limit
        }
        return self.contract_get(endpoint, payload=payload, is_private=True)

    def get_contract_trades(self, position, settle, limit):
        _settle = settle.lower()
        endpoint = f"/futures/{_settle}/trades"
        payload = {
            'contract': position + '_' + settle,
            'limit': limit
        }
        return self.contract_get(endpoint, payload, is_private=True)

    def get_contract_kline(self, position, settle, period, size):
        _settle = settle.lower()
        endpoint = f"/futures/{_settle}/candlesticks"
        payload = {
            'contract': position + '_' + settle,
            'interval': period,
            'limit': size
        }
        return self.contract_get(endpoint, payload, is_private=True)

    def get_contract_account(self, settle):
        _settle = settle.lower()
        endpoint = f"/futures/{_settle}/accounts"
        return self.contract_get(endpoint, payload=None, is_private=True)

    def get_contract_postion(self, position, settle):
        _settle = settle.lower()
        contract = position + '_' + settle
        endpoint = f"/futures/{_settle}/positions/{contract}"
        return self.contract_get(endpoint, payload=None, is_private=True)

    def submit_order(self, position, settle, price, size, order_type, external_oid='', params={}):
        _settle = settle.lower()
        endpoint = f'/futures/{_settle}/orders'

        payload = {
                    'contract': position + '_' + settle,
                    'price': price,
                    'size': size,
                    'tif': order_type #poc,gtc
                   }
        if size == 0:
            payload.update({'close': True})
        for key, value in params.items():
            payload.update({key: value})

        return self.contract_post(endpoint, payload, include_body=False, is_private=True)

    def cancel_order(self, settle, order_id):
        _settle = settle.lower()
        endpoint = f'/futures/{_settle}/orders/{order_id}'
        return self.contract_delete(endpoint, payload=None, include_body=False, is_private=True)

    def query_order(self, settle, order_id):
        _settle = settle.lower()
        endpoint = f'/futures/{_settle}/orders/{order_id}'
        return self.contract_get(endpoint, payload=None, include_body=False, is_private=True)

    # _from/_to: 'spot', 'margin', 'delivery', 'futures'
    def transfer_asset(self, currency, _from, _to, amount, currency_pair):
        endpoint = f'/wallet/transfers'
        payload = {
                    'currency': currency,
                    'from': _from,
                    'to': _to,
                    'amount': amount,
                    'currency_pair': currency_pair,
                    'settle': currency
                   }
        return self.contract_post(endpoint, payload, include_body=False, is_private=True)

'''
#client = ContractClient(api_ky, secret_key)
#res = client.get_contract_depth('BTC', 'USDT')
#res = client.get_contract_kline('BTC', 'USDT', '4h', 3)
#res = client.get_contract_account('USDT')
#res = client.get_contract_postion('BTC', 'USDT')
#order = client.submit_order('BTC', 'USDT', '50000', 1, 'poc')#post_only limit
#order = client.submit_order('BTC', 'USDT', '0', -1, 'ioc')#market
#order = client.submit_order('BTC', 'USDT', '0', 0, 'ioc')#market close position
#order = client.query_order('USDT', order['id'])
#order = client.cancel_order('USDT', order['id'])
#print(order)
'''
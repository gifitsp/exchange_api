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


class Signature:
    def generate_signature(self, method, params, request_path):
        if request_path.startswith("http://") or request_path.startswith("https://"):
            host_url = urllib.parse.urlparse(request_path).hostname.lower()
            request_path = '/' + '/'.join(request_path.split('/')[3:])
        else:
            host_url = urllib.parse.urlparse(self.api_base).hostname.lower()
        sorted_params = sorted(params.items(), key=lambda d: d[0], reverse=False)
        encode_params = urllib.parse.urlencode(sorted_params)
        payload = [method, host_url, request_path, encode_params]
        payload = "\n".join(payload)
        payload = payload.encode(encoding="UTF8")
        secret_key = self.secret_key.encode(encoding="utf8")
        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature

    def sign(self, method, endpoint):
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        params = {}
        params.update({"AccessKeyId": self.access_key,
                       "SignatureMethod": "HmacSHA256",
                       "SignatureVersion": "2",
                       "Timestamp": timestamp})

        params["Signature"] = self.generate_signature(method, params, endpoint)
        return params

################################################################
class SpotClient(Signature):
    api_base = "https://api.huobi.pro"

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

    def spot_post(self, endpoint, payload, is_private=False):
        method = 'POST'
        url = f'{self.api_base}{endpoint}'
        data = json.dumps(payload)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        params = None
        if is_private is True:
            params = self.sign(method, endpoint)
        self.session.cookies.clear()
        resp = self.session.request(method, url, params=params, data=data, headers=headers, timeout=5, proxies=self.proxies)
        return resp.json()

    # from/to: 'pro', 'margin', 'futures'
    def transfer_asset(self, currency, _from, _to, amount, currency_pair):
        _type = 2
        if (_from == 'pro' and _to != 'margin') or (_from != 'margin' and _to == 'pro'):
            _type = 1
            endpoint = f"/v1/futures/transfer"
        elif _from == 'pro' and _to == 'margin':
            endpoint = f"/v1/dw/transfer-in/margin"
        elif _from == 'margin' and _to == 'pro':
            endpoint = f"/v1/dw/transfer-out/margin"

        if _type == 1:
            payload = {
                'currency': currency,
                'amount': str(amount),
                'type': _from + '-to-' + _to,
            }
        elif _type == 2:
            payload = {
                'currency': currency,
                'amount': str(amount),
                'symbol': currency_pair,
            }
        return self.spot_post(endpoint, payload, is_private=True)

    # from/to: 'spot', 'swap', 'linear-swap'
    # mode: 'isolated', 'cross'
    def transfer_swap_asset(self, currency, _from, _to, amount, currency_pair, mode='isolated'):
        endpoint = '/v2/account/transfer'

        payload = {
            'from': _from,
            'to': _to,
            'currency': currency,
            'amount': float(amount),
        }

        if 'linear' in _from or 'linear' in _to:
            if mode != 'cross':
                payload.update({'margin-account': currency_pair})
            else:
                payload.update({'margin-account': 'USDT'})
        return self.spot_post(endpoint, payload, is_private=True)

################################################################
class ContractClient(Signature):
    api_base = "https://api.hbdm.com"

    VERSION = "1.1.5_201217_alpha"
    USER_AGENT = "AlphaQuant" + VERSION

    def __del__(self):
        if self.session:
            self.session.close()

    def __init__(self, access_key="",  secret_key="", api_base="", settle='', **kwargs):
        self.session = Session()
        self.access_key = access_key
        self.secret_key = secret_key
        if api_base:
            self.api_base = api_base.rstrip('/')
        self.proxies = kwargs.get('proxies', {})

        if settle == 'USD':
            self.METHOD_EX = 'swap-ex'
            self.METHOD_API = 'swap-api'
        else:
            self.METHOD_EX = 'linear-swap-ex'
            self.METHOD_API = 'linear-swap-api'

    def contract_get(self, endpoint, payload=None):
        payload = dict() if payload is None else payload
        url = f'{self.api_base}{endpoint}'
        p_str = urllib.parse.urlencode(sorted(payload.items()))
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': self.USER_AGENT
        }
        url = f'{url}?{p_str}' if p_str else url
        self.session.cookies.clear()
        resp = self.session.request('GET', url, headers=headers, timeout=5, proxies=self.proxies)
        return resp.json()

    def contract_post(self, endpoint, payload, is_private=False):
        method = 'POST'
        url = f'{self.api_base}{endpoint}'
        data = json.dumps(payload)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': self.USER_AGENT
        }

        params = None
        if is_private is True:
            params = self.sign(method, endpoint)
        self.session.cookies.clear()
        resp = self.session.request(method, url, params=params, data=data, headers=headers, timeout=5, proxies=self.proxies)
        return resp.json()

    def get_contract_depth(self, symbol, limit=1):
        endpoint = f'/{self.METHOD_EX}/market/depth'
        if limit is None:
            limit = 0
        return self.contract_get(endpoint, payload={f'contract_code':symbol, 'type': f'step{limit}'})

    def get_contract_trades(self, symbol, limit=1):
        endpoint = f'/{self.METHOD_EX}/market/history/trade'
        if limit is None:
            limit = 0
        return self.contract_get(endpoint, payload={f'contract_code':symbol, 'size': limit})

    def get_contract_kline(self, symbol, period, size):
        endpoint = f"/{self.METHOD_EX}/market/history/kline"
        payload = {
            'contract_code': symbol,
            'period': period,
            'size': size
        }
        return self.contract_get(endpoint, payload)

    def get_contract_account(self, symbol, type=''):
        if type != 'cross':
            endpoint = f"/{self.METHOD_API}/v1/swap_account_position_info"
        else:
            endpoint = f"/{self.METHOD_API}/v1/swap_cross_account_position_info"

        payload = {
            'contract_code': symbol
        }
        return self.contract_post(endpoint, payload, is_private=True)

    def submit_order(self, symbol, price, size, side, offset, order_type, open_type='',
                     leverage=1, external_oid=''):
        if open_type != 'cross':
            endpoint = f"/{self.METHOD_API}/v1/swap_order"
        else:
            endpoint = f"/{self.METHOD_API}/v1/swap_cross_order"

        payload = {
            'contract_code': symbol,
            'client_order_id': external_oid if external_oid else '',
            'price': price,
            'volume': size,
            'direction': side,
            'offset': offset,
            'lever_rate': leverage,
            'order_price_type': order_type
        }
        return self.contract_post(endpoint, payload, is_private=True)

    def cancel_order(self, order_id, symbol, open_type=''):
        if open_type != 'cross':
            endpoint = f"/{self.METHOD_API}/v1/swap_cancel"
        else:
            endpoint = f"/{self.METHOD_API}/v1/swap_cross_cancel"

        payload = {
            'contract_code': symbol,
            'order_id': order_id
        }
        return self.contract_post(endpoint, payload, is_private=True)

    def query_order(self, order_id, symbol, open_type=''):
        if open_type != 'cross':
            endpoint = f"/{self.METHOD_API}/v1/swap_order_info"
        else:
            endpoint = f"/{self.METHOD_API}/v1/swap_cross_order_info"

        payload = {
            'contract_code': symbol,
            'order_id': order_id
        }
        return self.contract_post(endpoint, payload, is_private=True)

'''
#client = ContractClient(api_key, secret_key, 'http://api.btcgateway.pro', settle='USDT')# or 'USD'
#res = client.get_contract_depth('BTC-USDT', 1)
#res = client.get_contract_kline('BTC-USDT', '4hour', 3)
#res = client.get_contract_account('BTC-USDT')
#order = client.submit_order('BTC-USDT', '50000', 1, 'buy', 'open', 'post_only', open_type='isolated', leverage=3)
#order = client.cancel_order(order['id'], 'BTC-USDT', open_type='isolated') or 'cross'
#order = client.query_order(order['id'], 'BTC-USDT', open_type='isolated')
#print(order)
'''
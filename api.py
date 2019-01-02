import time
import json
import requests
import urllib, http.client
import hmac, hashlib

from colors import *
from defs import *
from config import *
from keys import *

API_URL = 'bittrex.com'
API_VERSION = 'v1.1'

class ScriptError(Exception):
    pass


def call_api(**kwargs):
    http_method = kwargs.get('http_method') if kwargs.get('http_method', '') else 'GET'
    method = kwargs.pop('method')
    payload = {}

    if kwargs:
        payload.update(kwargs)

    nonce = str(int(round(time.time())))
    uri = "https://" + API_URL + "/api/" + API_VERSION + method + '?apikey=' + API_KEY + '&nonce=' + nonce
    uri += '&' + urllib.parse.urlencode(payload)

    apisign = hmac.new(API_SECRET,
                       uri.encode(),
                       hashlib.sha512).hexdigest()

    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Key": API_KEY,
               "apisign": apisign}

    conn = http.client.HTTPSConnection(API_URL, timeout=60)
    conn.request(http_method, uri, {}, headers)
    response = conn.getresponse().read()

    conn.close()

    try:
        obj = json.loads(response.decode('utf-8'))

        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        raise ScriptError('Request failed', response)
    
    
def cancel_order(uuid, order_type=''):
    cancel_res = call_api(method="/market/cancel", uuid=uuid)
    if cancel_res['success']:
        print(CGREEN, "\t\t%s order %s successfully canceled%s" % (order_type, uuid, CEND))
    else:
        print(CRED, "\t\t%s order %s cancelation failed (%s)%s" % (order_type, uuid, cancel_res['message'], CEND))
        
    return cancel_res['success']

def get_rate(market, order_type):
    # try to sell as higher as possible rate, 3 approaches:
    
    # 1. current ticker value for 'ask'/'bid'
    # 2. current ticker value +/- some little amount to be best advise
    # 3. ticker value 'last' 
    ticker_data = call_api(method="/public/getticker", market=market)
    #adjuster = (ticker_data['result']['Ask'] - ticker_data['result']['Bid']) / 100
    #if adjuster < ONE_SATOSHI:
    adjuster = ONE_SATOSHI    

    if order_type.lower() == 'sell':
        rate = float(ticker_data['result']['Ask'] - adjuster)
    else:
        rate = float(ticker_data['result']['Bid'] + adjuster)
   
    return rate * DEBUG_PRICE_RATE


def create_order(order_type, market, quantity, rate=None):
    method = "/market/" + order_type.lower() + ORDERS_TYPE
    rate = get_rate(market, order_type) if rate == None else rate
    responce = call_api(method=method, market=market, quantity=quantity, rate=rate)
    if responce['success']:        
        print(CGREEN, "\t\t\tsuccessfyly created %s order for %s, rate: %0.8f, quantity %0.8f uuid=%s%s"
            % (order_type.upper(), market, rate, quantity, responce['result']['uuid'], CEND))
    else:
        print(CRED, "\t\t\tfailed to create %s order: %s%s" % (order_type.upper(), responce['message'], CEND))
    
    return responce['success']

def create_buy(market, quantity=0):
    current_rate = None
    if not quantity:
        base = 'USDT' if market.split('-')[0] == 'USDT' else 'BTC'
        balance = call_api(method='/account/getbalance', currency=base)
        if balance['result']:
            base_available = float(balance['result']['Available'])

        if base_available:
            # TODO: think about order total algorithm (% of overall balance or fixed amount)
            # currently buy BTC for entire USDT balance
            # buy altcoin for 2% of entire balance
            current_rate = get_rate(market, 'buy')
            quantity = base_available / current_rate

            if market != 'USDT-BTC':
                # buy altcoin for 2% of available funds or minimum trade allowed
                if quantity * 0.02 > MIN_TRADE_ALLOWED:
                    quantity *= 0.02
                elif quantity > MIN_TRADE_ALLOWED:
                    quantity = MIN_TRADE_ALLOWED

            # round down
            adjuster = pow(10, ROUND_PRECISION)
            quantity = int(quantity * adjuster)
            quantity = float(quantity / adjuster)

    if quantity >= MIN_TRADE_ALLOWED:
        create_order("buy", market=market, quantity=quantity, rate=current_rate)
    else:
        print(CRED, '\t\tinsuficient funds to create BUY order, %s available: %0.8f%s' % (base, base_available, CEND))


def create_sell(market, quantity=0):
    create_order('sell', market=market, quantity=quantity)

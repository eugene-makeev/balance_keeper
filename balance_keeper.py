import time
import json
import requests
import urllib, http.client
import hmac, hashlib
#import sqlite3
import numpy
import talib

from keys import *
from colors import *
from logger import *
from timeframe import *

#from datetime import datetime

API_URL = 'bittrex.com'
API_VERSION = 'v1.1'

DEBUG_PRICE_RATE = 1.0

TRADE_HISTORY_SIZE_DAYS = 10

MACD_HIST_ZERO_DRIFT_THRESHOLD = 1.0

ONE_SATOSHI = 0.00000001
FIVE_SATOSHI = ONE_SATOSHI * 5
TEN_SATOSHI = ONE_SATOSHI * 10
MIN_VALUE_50K_SAT = ONE_SATOSHI * 50000
MIN_TRADE_ALLOWED = MIN_VALUE_50K_SAT

MIN_COMPETITOR_ORDER_VOLUME = 0.007
ROUND_PRECISION = 4

MACD_ADVICE_UPDATE_TIME = 1 * 60

ORDER_TYPE = 'limit'


TRUSTED_MARKETS = [
    'USDT-BTC']#, 'BTC-TRX', 'BTC-ADA', 'BTC-XRP', 'BTC-RDD', 'BTC-STORM', 'BTC-ZRX', 'BTC-BTG', 'BTC-POWR', 'BTC-BCH',
    #'BTC-QTUM', 'BTC-OMG', 'BTC-PAY', 'BTC-MCO', 'BTC-ZEN', 'BTC-SC', 'BTC-NEO', 'BTC-ETC', 'BTC-WAVES', 'BTC-LSK',
    #'BTC-EMC2', 'BTC-XLM', 'BTC-ETH', 'BTC-XEM', 'BTC-NAV', 'BTC-XMR', 'BTC-NXT', 'BTC-LTC'
#]


# global data
markets_supported = []
chart_data = {}
macd_advices = {}
#available = {}

g_open_orders = 0


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


def pull_historical_data(market, timeframe='hour'):
    # https://www.reddit.com/r/Bittrex/comments/7nrzeu/bittrex_historical_data/
    # If anyone is looking to pull historical data from Bittrex for a bot this is all the information I have found.
    # Full history:
    # https://bittrex.com/Api/v2.0/pub/market/GetTicks?marketName=BTC-WAVES&tickInterval=thirtyMin&_=1499127220008
    # Latest tick:
    # https://bittrex.com/Api/v2.0/pub/market/GetLatestTick?marketName=BTC-WAVES&tickInterval=onemin&_=1499127220008
    # Tick rates:
    # "oneMin", "fiveMin", "thirtyMin", "hour" and "day"
    get_ticks_url = "https://bittrex.com/Api/v2.0/pub/market/GetTicks?marketName=" + market + "&tickInterval="
  
    print('pull_historical_data')
  
    if market not in chart_data:
        chart_data[market] = {}
#        # pull data for closed timeframes
#        res = requests.get(get_ticks_url + timeframe)
#        for item in json.loads(res.text)['result']:
#            tf = get_time_from_str(item['T'])
#            chart_data[market][tf] = {'open': float(item['O']), 'close': float(item['C']), 'high': float(item['H']),
#                                      'low': float(item['L']), 'vol': float(item['V']), 'bvol': float(item['BV'])}
                    
    current_tf = get_current_timeframe(timeframe)
    
    if current_tf not in chart_data[market]:
        # pull data for closed timeframes
        res = requests.get(get_ticks_url + timeframe)
        if res.ok:
            chart_data[market].clear()
            for item in json.loads(res.text)['result']:
                chart_data[market][get_time_from_str(item['T'])] = \
                    {'open': float(item['O']), 'close': float(item['C']),
                     'high': float(item['H']), 'low': float(item['L']),
                     'vol': float(item['V']),  'bvol': float(item['BV'])}
        else:
            print('error retrieve trade data')
    else:
        del chart_data[market][current_tf]
                
    # pull data for current timeframe by smaller timeframes
    smaller_tf = 'hour' if timeframe == 'day' else 'oneMin'
    res = requests.get(get_ticks_url + smaller_tf)
    if res.ok:
    # merge data to match original timeframe
        for item in json.loads(res.text)['result']:
            if current_tf == get_timeframe_from_str(item['T'], timeframe):
                print('add 1 min data:', item)
                if current_tf not in chart_data[market]:
                    chart_data[market][current_tf] = \
                        {'open': float(item['O']), 'close': float(item['C']),
                         'high': float(item['H']), 'low': float(item['L']),
                         'vol': float(item['V']),  'bvol': float(item['BV'])}
                else:
                    chart_data[market][current_tf]['close'] = float(item['C'])
                    chart_data[market][current_tf]['vol'] += float(item['V'])
                    chart_data[market][current_tf]['bvol'] += float(item['BV'])
                    if chart_data[market][current_tf]['high'] < float(item['H']):
                        chart_data[market][current_tf]['high'] = float(item['H'])
                        if chart_data[market][current_tf]['low'] > float(item['L']):
                            chart_data[market][current_tf]['low'] = float(item['L'])
    else:
        print('error retrieve current timeframe data:', res.status_code)
    
    print('current timeframe data:', chart_data[market][current_tf])

    # add recent (last minute) trades into current timeframe
    if smaller_tf == 'oneMin':
        res = requests.get("https://bittrex.com/api/v1.1/public/getmarkethistory?market=" + market)
        if res.ok:
            current_smaller_tf = get_current_timeframe(smaller_tf)
            for trade in reversed(json.loads(res.text)['result']):
                if current_smaller_tf == get_timeframe_from_str(trade['TimeStamp'], smaller_tf):
                    chart_data[market][current_tf]['close'] = float(trade['Price'])
                    chart_data[market][current_tf]['vol'] += float(trade['Quantity'])
                    chart_data[market][current_tf]['bvol'] += float(trade['Total'])
                    if chart_data[market][current_tf]['high'] < float(trade['Price']):
                        chart_data[market][current_tf]['high'] = float(trade['Price'])
                        if chart_data[market][current_tf]['low'] > float(trade['Price']):
                            chart_data[market][current_tf]['low'] = float(trade['Price'])
                print('add trade:', trade)
        else:
            print('error retrieve recent trade:', res.status_code)

    print('resulted timeframe data:', chart_data[market][current_tf])

# get the trade history data
def get_ticks(market, timeframe='hour'):
    pull_historical_data(market, timeframe)
    return chart_data[market]

def get_macd_advice(chart_data):
    macd, macdsignal, macdhist = talib.MACD(numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)]),
                                            fastperiod=12, slowperiod=26, signalperiod=9)

    advise = 'wait'

    last_cross = numpy.argwhere(numpy.diff(numpy.sign(macdhist))).reshape(-1)[-1]
    print('macd: \t', macd[-1], '\tmacdsignal:', macdsignal[-1], '\tmacd_hist:', macdhist[-1])
    print('      \t', macd[last_cross], '\t           ', macdsignal[last_cross], '\t          ', macdhist[last_cross])

    #TODO: analyze macd and macdsignal zero cross
    #TODO: analyze time of average price around one value
    #TODO: analyze last candle bull/bear and do not sell/buy accordingly
    
    if abs(macdhist[last_cross]) + abs(macdhist[last_cross + 1]) > MACD_HIST_ZERO_DRIFT_THRESHOLD \
            or abs(macdhist[-1]) > MACD_HIST_ZERO_DRIFT_THRESHOLD:
        if macdhist[last_cross] < 0:
            #if macdsignal[-1] > macdsignal[-2] and macd[-1] > macd[-2]:
            advise = 'buy'
        else:
            #if macdsignal[-1] < macdsignal[-2] and macd[-1] < macd[-2]:
            advise = 'sell'
    return advise


def update_macd_advices():
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                            UPDATE MACD ADVICES
    ///////////////////////////////////////////////////////////////////////////////////
    ''')
    for market in TRUSTED_MARKETS:
        if market in markets_supported:
            macd_advices[market] = get_macd_advice(get_ticks(market))
        else:
            print(CRED, 'invalid market in trusted markets:', market, CEND)
    print('   ', macd_advices)

def cancel_order(uuid, order_type=''):
    cancel_res = call_api(method="/market/cancel", uuid=uuid)
    if cancel_res['success']:
        global g_open_orders
        g_open_orders -= 1
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
    method = "/market/" + order_type.lower() + ORDER_TYPE
    rate = get_rate(market, order_type) if rate == None else rate
    responce = call_api(method=method, market=market, quantity=quantity, rate=rate)
    if responce['success']:
        global g_open_orders
        g_open_orders += 1        
        print(CGREEN, "\t\t\tsuccessfyly created %s order for %s, rate: %0.8f, quantity %0.8f uuid=%s%s"
            % (order_type.upper(), market, rate, quantity, responce['result']['uuid'], CEND))
    else:
        print(CRED, "\t\t\tfailed to create %s order: %s%s" % (order_type.upper(), responce['message'], CEND))

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
        

def is_rate_changed(order):
    order_type = order["OrderType"].lower().split('_')[-1]
    # check competitor order validity
    order_book = call_api(method="/public/getorderbook", market=order['Exchange'], type=order_type)
    if order_book['success']:
        for competitor in order_book['result']:
            if competitor['Rate'] != order['Limit']:
                # TODO: ckeck if MIN_COMPETITOR_ORDER_VOLUME is suitable for altcoins
                if competitor['Quantity'] >= MIN_COMPETITOR_ORDER_VOLUME:
                    return True
            else:
                return False
    else:
        print('failed to get order book data')
        
    return False
                

def adjust_open_orders(create_new=True):
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                            ADJUST OPEN ORDERS
    ///////////////////////////////////////////////////////////////////////////////////
    ''')
    orders = call_api(method='/market/getopenorders')
    if orders['success']:
        global g_open_orders
        g_open_orders = len(orders['result'])
        print('\tOpen orders:', g_open_orders)
        for order in orders['result']:
            opened = get_time_from_str(order['Opened'])
            print('\t%s %s, quantity: %0.8f, created: %s' % (order["OrderType"], order['Exchange'],
                                                             order['QuantityRemaining'], opened))
            if is_rate_changed(order):
                order_type = order["OrderType"].split('_')[-1]
                if cancel_order(order['OrderUuid'], order_type) and create_new:
                    quantity = order['QuantityRemaining']
                    if order_type == 'SELL':
                        create_sell(order['Exchange'], quantity)
                    else:
                        create_buy(order['Exchange'], quantity)
    else:
        print(CRED, "failed to get open orders:", orders['message'], CEND)


def stop_loss_protection():
    #------ get available currencies and check
    # get closed orders list
    for market in TRUSTED_MARKETS:
        closed_orders = call_api(method='/market/getorderhistory&market=' + market)
        if closed_orders['success']:
            last_order = closed_orders['result'][0]
            order_type = last_order["OrderType"].lower().split('_')[-1]
            get_rate(market, order_type)
                
    # if current price gets lower/higher of the closed order price + fee then close position if funds available

def manage_balances():
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                             MANAGE BALANCES
    ///////////////////////////////////////////////////////////////////////////////////
    ''')
    btc_advise = macd_advices['USDT-BTC']  #get_macd_advice(get_ticks('USDT-BTC'))

    balances = call_api(method='/account/getbalances')
    if balances['success']:
        for balance in balances['result']:
            if balance['Available'] and balance['Currency'] == 'BTC':  #balance['Currency'] != 'USDT':
                print('\t* working with currency %s: %f available' % (balance['Currency'], balance['Available']))
                # try to sell to USDT if BTC is failing to avoid double fees
                base = 'USDT-' if btc_advise == 'sell' or balance['Currency'] == 'BTC' else 'BTC-'
                market = base + balance['Currency']

                if balance['Currency'] == 'BTC':
                    advise = btc_advise
                else:
                    if market not in markets_supported:
                        market = 'BTC-' + balance['Currency']
                    # just in case some currencies not in trusted markets
                    if market in TRUSTED_MARKETS:
                        advise = macd_advices[market]
                    else:
                        advise = get_macd_advice(get_ticks(market))

                print('\tadvise for %s is %s' % (market, advise))
                if advise == 'sell':
                    create_sell(market, balance['Available'])
                #elif advise == 'buy':
                #    create_buy(market, balance['Available'])

    else:
        print('Error retrieving the balances information %s' % balances['message'])

# currently work only with trusted markets by MACD advice
def make_balances():
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                               MAKE BALANCES
    ///////////////////////////////////////////////////////////////////////////////////
    ''')
    for market in TRUSTED_MARKETS:
        if market in markets_supported:
            advise = macd_advices[market]  #get_macd_advice(get_ticks(market))
            print('\tadvise for %s is %s' % (market, advise))
            if advise == 'buy':
                create_buy(market)
        else:
            print(CRED, '\tUnknown market in TRUSTED_MARKETS:', market, CEND)


############################################################################################
#  Main Loop
############################################################################################
numpy.seterr(all='ignore')


# print all available markets
markets = call_api(method='/public/getmarkets')
if markets['success']:
    for pair in markets['result']:
        markets_supported.append(pair['MarketName'])
    print(markets_supported)
else:
    print("Api doesn't work")
    SystemExit()

start = True

# sync start time with the chart data update intervals
start_time = int(numpy.ceil(time.time() / MACD_ADVICE_UPDATE_TIME)) * MACD_ADVICE_UPDATE_TIME

while True:
    try:
        # 0. cancel all open orders since they are most likely not actual anymore
        # 1. check current orders, if order is not executed in ORDER_LIFE_TIME, adjust price
        # TODO: move to separate thread
        #if g_open_orders or start:
        adjust_open_orders(not start)
        # stop loss
        #stop_loss_protection()
        # 2. get MACD advises on start and every MACD_ADVICE_UPDATE_TIME min
        current_time = time.time()
        if start or (current_time - start_time) >= MACD_ADVICE_UPDATE_TIME:
            start_time = current_time
            update_macd_advices()
            # 3. check balances and sell if advised
            if 'sell' in macd_advices.values():
                manage_balances()
            # 4. find the good currency to buy if there is available USDT or BTC balances
            #    the maximum amount to by is some % of overall balance TBD.
            if 'buy' in macd_advices.values():
                make_balances()

        start = False
        if g_open_orders:
            time.sleep(1)
        else:
            time.sleep(5)

    except Exception as e:
        print(e)


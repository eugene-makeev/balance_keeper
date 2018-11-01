import time
import json
import requests
import urllib, http.client
import hmac, hashlib
#import sqlite3
import numpy
import talib

#from datetime import datetime

from mpl_finance import candlestick2_ohlc
import matplotlib.animation as animation

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


CEND      = '\33[0m'
CBOLD     = '\33[1m'
CITALIC   = '\33[3m'
CURL      = '\33[4m'
CBLINK    = '\33[5m'
CBLINK2   = '\33[6m'
CSELECTED = '\33[7m'

CBLACK  = '\33[30m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[34m'
CVIOLET = '\33[35m'
CBEIGE  = '\33[36m'
CWHITE  = '\33[37m'

CBLACKBG  = '\33[40m'
CREDBG    = '\33[41m'
CGREENBG  = '\33[42m'
CYELLOWBG = '\33[43m'
CBLUEBG   = '\33[44m'
CVIOLETBG = '\33[45m'
CBEIGEBG  = '\33[46m'
CWHITEBG  = '\33[47m'

CGREY    = '\33[90m'
CRED2    = '\33[91m'
CGREEN2  = '\33[92m'
CYELLOW2 = '\33[93m'
CBLUE2   = '\33[94m'
CVIOLET2 = '\33[95m'
CBEIGE2  = '\33[96m'
CWHITE2  = '\33[97m'

CGREYBG    = '\33[100m'
CREDBG2    = '\33[101m'
CGREENBG2  = '\33[102m'
CYELLOWBG2 = '\33[103m'
CBLUEBG2   = '\33[104m'
CVIOLETBG2 = '\33[105m'
CBEIGEBG2  = '\33[106m'
CWHITEBG2  = '\33[107m'

from keys import *

ORDER_LIFE_TIME = 0.5 * 60

API_URL = 'bittrex.com'
API_VERSION = 'v1.1'

DEBUG_PRICE_RATE = 1.0
OPEN_PRICE_RATE = 1.0025     #try to cover fees
REOPEN_PRICE_RATE = 1.0  #try to cover comission
TRADE_HISTORY_SIZE_DAYS = 10
MAX_CANDLES_BEFORE_ADVICE_WAIT = 5
MACD_HIST_ZERO_DRIFT_THRESHOLD = 2.9

MIN_VALUE_50K_SAT = 0.00000001 * 50000
MIN_TRADE_ALLOWED = MIN_VALUE_50K_SAT

ROUND_PRECISION = 4

MACD_ADVICE_UPDATE_TIME = 1 * 60

NUM_OF_CHANGING_MACDH_CANDLES_TO_MAKE_ORDER = 2

MACD_SELL_MIN_LEVEL = 0.005
MACD_BUY_MAX_LEVEL = -0.005


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


def call_api(**kwargs):
    http_method = kwargs.get('http_method') if kwargs.get('http_method', '') else 'POST'
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

def get_timeframe_seconds(timeframe, multiplier=1):
    timeframe_seconds = 60
    if timeframe == 'day':
        timeframe_seconds *= 24 * 60 * multiplier
    elif timeframe == 'hour':
        timeframe_seconds *= 60 * multiplier
    elif timeframe == 'thirtyMin':
        timeframe_seconds *= 30
    elif timeframe == 'fiveMin':
        timeframe_seconds *= 5

    return timeframe_seconds

def get_time_from_str(timestr):
    try:
        t = time.strptime(timestr, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        t = time.strptime(timestr, '%Y-%m-%dT%H:%M:%S')
    return int(time.mktime(t))

def get_timestamp(timestr):
    return int(get_time_from_str(timestr))

def get_current_timeframe(timeframe):
    seconds = get_timeframe_seconds(timeframe)
    return numpy.ceil(time.mktime(time.gmtime(time.time())) / seconds) * seconds

def get_timeframe_from_str(timestr, timeframe):
    seconds = get_timeframe_seconds(timeframe)
    return int(numpy.ceil(get_time_from_str(timestr) / seconds) * seconds)


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

    # retrieve the latest trades that have occured for a specific market
    # new_data_started = False
    # res = requests.get("https://bittrex.com/api/v1.1/public/getmarkethistory?market=" + market)
    # for trade in reversed(json.loads(res.text)['result']):
    #     try:
    #         dt_obj = datetime.strptime(trade['TimeStamp'], '%Y-%m-%dT%H:%M:%S.%f')
    #     except ValueError:
    #         dt_obj = datetime.strptime(trade['TimeStamp'], '%Y-%m-%dT%H:%M:%S')
    #     ts = int(numpy.ceil(time.mktime(dt_obj.timetuple()) / timeframe_in_sec)) * timeframe_in_sec  # round up to timeframe
    #
    #     if ts not in chart_data[market]:
    #         chart_data[market][ts] = {'open': float(trade['Price']), 'close': 0.0, 'high': 0.0,
    #                                   'low': float(trade['Price']), 'vol': 0.0, 'bvol': 0.0}
    #         new_data_started = True
    #
    #     if new_data_started:
    #         chart_data[market][ts]['close'] = float(trade['Price'])
    #         chart_data[market][ts]['vol'] += float(trade['Quantity'])
    #         chart_data[market][ts]['bvol'] += float(trade['Total'])
    #         if chart_data[market][ts]['high'] < float(trade['Price']):
    #             chart_data[market][ts]['high'] = float(trade['Price'])
    #         if chart_data[market][ts]['low'] > float(trade['Price']):
    #             chart_data[market][ts]['low'] = float(trade['Price'])
    # print(ts, chart_data[market][ts])
    return chart_data[market]  #if int(time.mktime(time.gmtime(time.time())) - ts) >= 1800 else chart_data[market][:-1]

def get_simple_macd_advice(chart_data):
    macd, macdsignal, macdhist = talib.MACD(numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)]),
                                            fastperiod=12, slowperiod=26, signalperiod=9)

    advise = 'wait'

    last_cross = numpy.argwhere(numpy.diff(numpy.sign(macdhist))).reshape(-1)[-1]
    if macdhist[last_cross] < 0:
        advise = 'buy'
    else:
        advise = 'sell'

    return advise

def check_strategy_profit(chart_data):
    close_array = numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)])
    macd, macdsignal, macdhist = talib.MACD(close_array, fastperiod=12, slowperiod=26, signalperiod=9)

    crosses = numpy.argwhere(numpy.diff(numpy.sign(macdhist))).reshape(-1)

    available_btc = 0.0
    was_usdt = 0.0
    available_usdt = 0.0
    min_sell_price = 0
    profit = 0.0
    buy_price = 0
    buys = []
    sells = []

    for offset, macdh in enumerate(macdhist):
        if offset in crosses and not numpy.isnan(macdh):
            # macdh is changing it's sign somewhere in between this timeframe and next
            # so current sign is opposite to trend direction
            if macdh < 0 and not buy_price:
                buy_price = close_array[offset]
                if not was_usdt:
                    was_usdt = buy_price * 1.0025
                    available_btc = 1.0
                else:
                    available_btc = (available_usdt / buy_price) / 1.0025
                    available_usdt = 0.0
                buys.append(macd[offset])
                sells.append(numpy.nan)
                print('BUY:', buy_price)
            elif macdh > 0 and buy_price:
                sell_price = close_array[offset]
                print('SELL:', sell_price)
                sells.append(macd[offset])
                buys.append(numpy.nan)
                available_usdt = (sell_price * available_btc) / 1.0025
                available_btc = 0.0
                buy_price = 0
        else:
            buys.append(numpy.nan)
            sells.append(numpy.nan)

    print('was', was_usdt)
    print('now_usdt', available_usdt)
    print('now_btc', available_btc)
    if available_btc:
        print('profit:', available_btc - 1)
    else:
        print('profit_usdt', available_usdt - was_usdt)

    # MACD
    ax.clear()
    ax.plot(macd[-200:], color="y")
    ax.plot(macdsignal[-200:])
    ax.plot(buys[-200:], 'go')
    ax.plot(sells[-200:], 'ro')
    #plt.show()

def get_last_abs_max(macdhist):
    abs_max = 0.0
    for macdh in macdhist:
        abs_val = abs(macdh)
        if abs_val > abs_max:
            abs_max = abs_val
    return abs_max

def get_macd_advice(chart_data):
    macd, macdsignal, macdhist = talib.MACD(numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)]),
                                            fastperiod=12, slowperiod=26, signalperiod=9)

    advise = 'wait'

    last_cross = numpy.argwhere(numpy.diff(numpy.sign(macdhist))).reshape(-1)[-1]
    print('macd: \t', macd[-1], '\tmacdsignal:', macdsignal[-1], '\tmacd_hist:', macdhist[-1])
    print('      \t', macd[last_cross], '\t           ', macdsignal[last_cross], '\t          ', macdhist[last_cross])
    #last_two_crosses = numpy.argwhere(numpy.diff(numpy.sign(macdhist))).reshape(-1)[-2:]
    #prev_abs_max_macdh = get_prev_abs_max(macdhist[last_two_crosses[0]:last_two_crosses[1]])
    
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


    #if macdhist.size - last_cross < MAX_CANDLES_BEFORE_ADVICE_WAIT:  # this is for first buy/sell


    # #trend = 'BULL' if macd[-1] > macdsignal[-1] else 'BEAR'
    #
    # make_order = False
    #
    # # the last trand change
    # #last_cross = numpy.argwhere(numpy.diff(numpy.sign(macdhist))).reshape(-1)
    #
    # # the simplest algorithm is to buy/sell on cross
    #
    #
    # make_order = False
    # max_abs_macdh = 0.0
    # local_max_abs_macdh = 0.0
    # prev_macdh = 0.0
    #
    # # check only candles passed after last macd and macds cross
    # for offset, macdh in enumerate(macdhist[last_cross:]):
    #     print(macdh)
    #     if macdh < 0:
    #         advise = 'buy'
    #     else:
    #         advise = 'sell'
    #
    #
    #
    #     # this is try to catch the trend reverse but it might be too early
    #     if abs(macdh) >= abs(max_abs_macdh):
    #         max_abs_macdh = macdh
    #         trend_changing = 0
    #     elif abs(macdh) >= abs(prev_macdh):
    #         trend_changing = 0
    #     else:
    #         trend_changing += 1
    #
    #     prev_macdh = macdh
    #
    #     if trend_changing >= NUM_OF_CHANGING_MACDH_CANDLES_TO_MAKE_ORDER:
    #         # additional check for % of maximum value
    #         perc = (macdh / max_abs_macdh) * 100
    #         if (macdh > 0 and perc > BULL_PERC) or (macdh < 0 and perc < (100 - BEAR_PERC)):
    #             make_order = True
    #         make_order = True
    #         print('macdhist is changing %d periods' % changing)
    #
    #
    # if trend == 'BEAR' and make_order:
    #     advise = 'buy'
    # elif trend == 'BEAR' or (trend == 'BULL' and make_order):
    #     advise = 'wait'
    # elif sell_time:
    #     advise = 'sell'

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
            print('invalid market in trusted markets: %s' % market)
    print('   ', macd_advices)


def create_buy(market, quantity=0):
    ticker_data = call_api(method="/public/getticker", market=market)
    current_rate = float(ticker_data['result']['Ask']) / DEBUG_PRICE_RATE

    if not quantity:
        base = ('USDT' if market.split('-')[0] == 'USDT' else 'BTC')
        balance = call_api(method='/account/getbalance', currency=base)
        if balance['result']:
            base_available = float(balance['result']['Available'])

        if base_available:
            # TODO: think about order total algorithm (% of overall balance or fixed amount)
            # currently buy BTC for entire USDT balance
            # buy altcoin for 2% of entire balance
            quantity = base_available / (current_rate * DEBUG_PRICE_RATE)

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
        print("\t\tcreate BUY order for %s, current rate: %0.8f, quantity %0.8f"
              % (market, current_rate, quantity))
        order_res = call_api(method="/market/buylimit", market=market, quantity=quantity, rate=current_rate)
        print("\t\t\tsuccess:", order_res['success'], order_res['message'])
    else:
        print('\t\tinsuficient funds to create order, %s available: %0.8f' % (base, base_available))


def create_sell(market, quantity=0):
    ticker_data = call_api(method="/public/getticker", market=market)
    current_rate = float(ticker_data['result']['Bid']) * DEBUG_PRICE_RATE

    # TODO: try to choose rate as high as possible (maybe using different idicators)
    print("\t\tcreate SELL order for %s, current rate: %0.8f, quantity %0.8f"
          % (market, current_rate, quantity))
    order_res = call_api(method="/market/selllimit", market=market, quantity=quantity, rate=current_rate)
    print("\t\t\tsuccess:", order_res['success'], order_res['message'])


def cancel_orders(orders_type='ALL'):
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                            CANCEL %s ORDERS
    ///////////////////////////////////////////////////////////////////////////////////
    ''' % type)
    orders = call_api(method='/market/getopenorders')
    if orders['success']:
        for order in orders['result']:
            order_type = order["OrderType"].split('_')[-1]
            if orders_type == 'ALL' or order_type == orders_type:
                print("\t* cancel %s order for %s" % (order_type, order['Exchange']))
                cancel_res = call_api(method="/market/cancel", uuid=order['OrderUuid'])
                print("\t\tsuccess:", cancel_res['success'], cancel_res['message'])
    else:
        print("failed to get open orders:", orders['message'])


def sell_all():
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                                SELL ALL
    ///////////////////////////////////////////////////////////////////////////////////
    ''')
    cancel_orders('BUY')

    balances = call_api(method='/account/getbalances')
    if balances['success']:
        for balance in balances['result']:
            if balance['Available']:
                if balance['Currency'] == 'BTC':
                    market = 'USDT-BTC'
                else:
                    market = 'USDT-' + balance['Currency']
                    if market not in markets_supported:
                        market = 'BTC-' + balance['Currency']
                create_sell(market, balance['Available'])

    sold_out = False
    while not sold_out:
        open_orders = adjust_open_orders()
        balance = call_api(method='/account/getbalance', currency='USDT-BTC')
        if balance['result']:
            btc_available = float(balance['result']['Available'])
            if btc_available:
                create_sell('USDT-BTC', btc_available)
            elif not open_orders:
                sold_out = True
        time.sleep(5)


# TODO: min price to sell is to return all the money back
def adjust_open_orders(create_new=True):
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                            ADJUST OPEN ORDERS
    ///////////////////////////////////////////////////////////////////////////////////
    ''')
    orders = call_api(method='/market/getopenorders')
    if orders['success']:
        print('\tOpen orders:', len(orders['result']))
        for order in orders['result']:
            print('\t%s %s, quantity: %0.8f, created: %s' % (order["OrderType"], order['Exchange'],
                                                             order['QuantityRemaining'], order['Opened']))
            try:
                opened = time.strptime(order['Opened'], "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                opened = time.strptime(order['Opened'], '%Y-%m-%dT%H:%M:%S')
            time_passed = int(time.mktime(time.gmtime(time.time())) - time.mktime(opened))
            if time_passed > ORDER_LIFE_TIME:
                order_type = order["OrderType"].split('_')[-1]
                print("\t* cancel %s order for %s (lifetime %d seconds)" % (order_type, order['Exchange'], time_passed))
                cancel_res = call_api(method="/market/cancel", uuid=order['OrderUuid'])
                print("\t\tsuccess:", cancel_res['success'], cancel_res['message'])
                if cancel_res['success'] and create_new:
                    quantity = order['QuantityRemaining']
                    if order_type == 'SELL':
                        create_sell(order['Exchange'], quantity)
                    else:
                        create_buy(order['Exchange'], quantity)
    else:
        print("failed to get open orders:", orders['message'])

    return len(orders['result'])

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

# this function will go over all the currencies
# to find some potentially good profit currencies
def get_the_best_advice():
    pass

# this function will go over all the available currerencies
# to find potentially low profit currencies
def get_the_worst_advice():
    pass

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
            print('\tUnknown market in TRUSTED_MARKETS:', market)


############################################################################################
#  Main Loop
############################################################################################
numpy.seterr(all='ignore')

fig, ax = plt.subplots(1, sharex=True)
plt.suptitle(TRUSTED_MARKETS[0])

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

#check_strategy_profit(get_ticks('USDT-BTC'))
# main function
#ani = animation.FuncAnimation(fig, update_data, interval=5000)
#plt.show()

while True:
    try:
        # 0. cancel all open orders since they are most likely not actual anymore
        # 1. check current orders, if order is not executed in ORDER_LIFE_TIME, adjust price
        # TODO: move to separate thread
        adjust_open_orders(not start)
        # 2. get MACD advises on start and every MACD_ADVICE_UPDATE_TIME min
        current_time = time.time()
        if start or (current_time - start_time) >= MACD_ADVICE_UPDATE_TIME:
            start_time = current_time
            update_macd_advices()
            # 3. check balances and sell if advised
            manage_balances()
            # 4. find the good currency to buy if there is available USDT or BTC balances
            #    the maximum amount to by is some % of overall balance TBD.
            make_balances()

        start = False
        time.sleep(5)

    except Exception as e:
        print(e)

from api import *
from config import *
from defs import *
from trade import *

markets_supported = {}

def sell_all():
    print('''
    ///////////////////////////////////////////////////////////////////////////////////
    //                                SELL ALL
    ///////////////////////////////////////////////////////////////////////////////////
    ''')
    cancel_orders('BUY')
    
    markets = call_api(method='/public/getmarkets')
    if markets['success']:
        for pair in markets['result']:
            markets_supported.append(pair['MarketName'])

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
            if btc_available and btc_available > MIN_TRADE_ALLOWED:
                create_sell('USDT-BTC', btc_available)
            elif not open_orders:
                sold_out = True
        time.sleep(5)
        
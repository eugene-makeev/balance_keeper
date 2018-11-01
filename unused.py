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

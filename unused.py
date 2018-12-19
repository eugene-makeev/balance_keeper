
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

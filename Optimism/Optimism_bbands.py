import numpy as np
import pandas as pd
import datetime as dt
import backtrader as bt
import matplotlib.pyplot as ply


class SOLStrategy(bt.Strategy):
    def __init__(self):
        # 初始化持仓数据
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.sellprice = None
        self.sellcomm = None
        self.buy_time = None
        self.sell_time = None
        self.long_count = 0
        self.short_count = 0
        # 定义K线数据
        self.close = self.datas[0].close
        self.high = self.datas[0].high
        self.low = self.datas[0].low
        self.open = self.datas[0].open
        # 定义 macd(12,26,9) 指标
        self.MACD = bt.indicators.MACD(self.datas[0], period_me1=12, period_me2=26, period_signal=9)
        self.macd = self.MACD.macd
        self.signal = self.MACD.signal
        self.hist = self.macd - self.signal
        # 定义 rsi 指标
        self.rsi = bt.indicators.RSI_SMA(self.datas[0], period=15)
        # 定义 ma 指标
        self.ma2 = bt.indicators.MovingAverageSimple(self.datas[0], period=2)
        self.ma20 = bt.indicators.MovingAverageSimple(self.datas[0], period=20)
        # 定义布林带指标
        self.bbands = bt.indicators.BollingerBands(self.datas[0], period=20, devfactor=2)
        self.upper = self.bbands.lines.top
        self.lower = self.bbands.lines.bot
        # 定义成交量指标
        self.vol = self.datas[0].volume
        # 初始化买入信息
        self.buy_signal = None
        self.sell_signal = None

    def next(self):

        ma2_delta = (self.ma2[0] - self.ma2[-1])
        last_ma2_delta = (self.ma2[-1] - self.ma2[-2])
        second_ma2_delta = (self.ma2[-2] - self.ma2[-3])

        lower_delta = self.lower[-1] - self.lower[0]
        last_lower_delta = self.lower[-2] - self.lower[-1]

        # 做多
        # 布林带策略 1：
        bbands_long = (self.close[0] > self.lower[0]) and \
                      (all(self.close[i] < self.lower[i] for i in range(-1, -4, -1))) and \
                      (all(self.close[i] < self.open[i] for i in range(-2, -5, -1))) and \
                      (any(self.vol[i] > 250000 for i in range(-1, -5, -1))) and \
                      (lower_delta < last_lower_delta)
        # 布林带策略 2：
        bbands_long_2 = (all(self.high[i] < self.ma20[i] for i in range(-1, -10, -1))) and \
                        (all(self.close[i] < self.lower[i] for i in range(-1, -3, -1))) and \
                        (self.hist[0] < 0) and (self.hist[0] > self.hist[-1]) and \
                        (all(self.vol[i] > 100000 for i in range(-1, -3, -1))) and \
                        (self.close[0] > self.open[0]) and (self.rsi[-1] < 35)
        # 做空
        # 布林带策略 1
        bbands_short = (self.close[0] < self.upper[0]) and \
                       (any(self.hist[i] > 0.05 for i in range(-1, -3, -1))) and \
                       (all(self.high[i] > self.upper[i] for i in range(-1, -4, -1))) and \
                       (all(self.close[i] > self.open[i] for i in range(-2, -4, -1))) and \
                       (any(self.vol[i] > 150000 for i in range(-1, -3, -1)))
        # 布林带策略 2
        bbands_short_2 = (all(self.low[i] > self.ma20[i] for i in range(0, -15, -1))) and \
                         (all(self.close[i] > self.upper[i] for i in range(-1, -3, -1))) and \
                         (self.hist[0] > 0) and self.rsi[0] > 55

        if not self.position:
            if bbands_long:
                self.buy_signal = 'bbands_long' if bbands_long else 'bbands_long_2'
                self.buy()
                self.long_count += 1
            # elif bbands_short or bbands_short_2:
            #     self.sell_signal = 'bbands_short' if bbands_short else 'bbands_short_2'
            #     self.sell()
            #     self.short_count += 1
        else:
            if self.position.size > 0:
                close_bbands_long = (self.close[0] > self.upper[0]) and (self.rsi[0] > 70)
                stop_bbands_long = self.close[0] < self.buyprice * 0.92
                close_bbands_2_long = (self.high[0] > self.upper[0]) and self.rsi[0] > 55
                stop_bbands_2_long = self.close[0] < self.buyprice * 0.94
                if self.buy_signal == 'bbands_long':
                    if close_bbands_long or stop_bbands_long:
                        self.sell()
                elif self.buy_signal == 'bbands_long_2':
                    if close_bbands_2_long or stop_bbands_2_long:
                        self.sell()

            elif self.position.size < 0:
                close_bbands_short = self.low[-1] < self.lower[-1] and (self.rsi[-1] < 45)
                stop_bbands_short = self.close[0] > self.sellprice * 1.08
                close_bbands_2_short = (self.low[0] < self.lower[0]) and self.rsi[0] < 50
                stop_bbands_2_short = self.close[0] > self.sellprice * 1.08
                if self.sell_signal == 'bbands_short':
                    if close_bbands_short or stop_bbands_short:
                        self.buy()
                elif self.sell_signal == 'bbands_short_2':
                    if close_bbands_2_short or stop_bbands_2_short:
                        self.buy()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log('BUY EXECUTED,Price:%.2f, Cost:%.2f, Comm: %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log('SELL EXECUTED,Price:%.2f, Cost:%.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))
                self.sellprice = order.executed.price
                self.sellcomm = order.executed.comm
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:  # 如果订单状态为‘取消’、‘保证金不足’或‘被拒绝’，则记录相应的状态。
            self.log('Order Canceled/Margin/Rejected')
        self.order = None  # 重新初始化订单状态

    def notify_trade(self, trade):
        if not trade.isclosed:  # 检查交易是否已经关闭，没有关闭则直接返回。
            return
        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                     (trade.pnl, trade.pnlcomm))

    def log(self, txt, dt=None, doprint=True):  # 输出一个日志，记录传入的 txt 和 dt。
        if doprint:
            dt = dt or self.datas[0].datetime.datetime(0)
            print('%s,%s' % (dt.isoformat(), txt))


if __name__ == '__main__':
    cerebro = bt.Cerebro()  # 初始化 Cerebro 引擎
    dataframe = pd.read_csv('SOLUSDT-5m-alldata.csv')  # 将 csv 文件读取为一个 Dataframe 对象
    dataframe['open_time'] = pd.to_datetime(dataframe['open_time'])  # 将 open_time 列转换为 datatime 类型
    dataframe.set_index('open_time', inplace=True)
    # 将K线数据加载给 cerebro 引擎
    data_SOLUSDT = bt.feeds.PandasData(
        dataname=dataframe,
        fromdate=dt.datetime(2021, 5, 18),
        todate=dt.datetime(2021, 8, 5),
        timeframe=bt.TimeFrame.Minutes,
        compression=5
    )

    cerebro.adddata(data_SOLUSDT)
    cerebro.addstrategy(SOLStrategy)
    # 夏普比率和最大回撤
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='SharpeRatio')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='DrawDown')
    # 设置初始资金和手续费
    cerebro.broker.setcash(1000.0)
    cerebro.broker.setcommission(commission=0.0004)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)
    result = cerebro.run()

    strategy = cerebro.runstrats[0][0]
    print('做多次数:', strategy.long_count)
    print('做空次数:', strategy.short_count)
    print('夏普比率：', result[0].analyzers.SharpeRatio.get_analysis()['sharperatio'])
    print('最大回撤：', result[0].analyzers.DrawDown.get_analysis()['max']['drawdown'])
    cerebro.plot()
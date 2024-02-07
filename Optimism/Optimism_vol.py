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

        global long_order_vol
        global short_order_vol

        ma2_delta = (self.ma2[0] - self.ma2[-1])
        last_ma2_delta = (self.ma2[-1] - self.ma2[-2])
        second_ma2_delta = (self.ma2[-2] - self.ma2[-3])

        lower_delta = (self.lower[-1] - self.lower[0])
        last_lower_delta = (self.lower[-2] - self.lower[-1])
        second_lower_delta = (self.lower[-3] - self.lower[-2])

        # 成交量策略：做多
        vol_long = (self.close[0] < self.open[0] and self.vol[0] > 450000) and \
                   (self.rsi[0] < 60) and (self.rsi[0] > 10) and (self.hist[0] < -0.01) and \
                   (self.low[0] < self.ma20[0]) and self.vol[-1] < (self.vol[0] * 0.75) and \
                   (self.low[-3] > self.low[-2] > self.low[-1])
        # 成交量策略：做空
        vol_short = (self.close[0] > self.open[0] and self.vol[0] > 350000) and \
                    (self.low[0] > self.ma20[0]) and (60 < self.rsi[0] < 90) and \
                    (self.vol[-1] < (self.vol[0] * 0.6)) and (self.hist[0] > 0)

        if not self.position:
            if vol_long:
                self.buy()
                long_order_vol = self.vol[0]
                self.buy_time = self.datetime.datetime()
                self.long_count += 1
            # if vol_short:
            #     self.sell()
            #     short_order_vol = self.vol[0]
            #     self.sell_time = self.datetime.datetime()
            #     self.short_count += 1
        else:
            if self.position.size > 0:

                time_diff = self.datetime.datetime() - self.buy_time
                close_vol_long = (self.ma2[0] < self.ma2[-1]) and (self.ma2[-1] > self.ma2[-2]) and (self.ma2[-2] > self.ma2[-3]) and \
                                 (ma2_delta < -0.05) and (last_ma2_delta > 0.015) and (second_ma2_delta > 0.001) and \
                                 (self.rsi[-1] > 20)
                close_vol_long_1 = close_vol_long and time_diff.total_seconds() > 3 * 5 * 60
                close_vol_long_2 = (self.close[0] > self.upper[0]) and self.rsi[0] > 80

                stop_vol_long = self.close[0] < self.buyprice * 0.94

                if close_vol_long_1 or close_vol_long_2 or stop_vol_long:
                    self.sell()
            elif self.position.size < 0:

                time_diff = self.datetime.datetime() - self.sell_time
                close_vol_short = (self.ma2[0] > self.ma2[-1]) and (self.ma2[-1] < self.ma2[-2]) and (self.ma2[-2] < self.ma2[-3]) and \
                                  (ma2_delta > 0.045) and (last_ma2_delta < -0.025) and (second_ma2_delta < -0.01)
                close_vol_short_1 = close_vol_short and time_diff.total_seconds() > 3 * 5 * 60
                close_vol_short_2 = (self.close[0] < self.open[0]) and (self.vol[0] > short_order_vol * 0.5) and \
                                    (self.close[0] < self.ma20[0])
                close_vol_short_3 = (self.low[0] < self.lower[0]) and self.rsi[0] < 25

                stop_vol_short = self.close[0] > self.sellprice * 1.04
                if close_vol_short_1 or close_vol_short_2 or close_vol_short_3 or stop_vol_short:
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
        fromdate=dt.datetime(2023, 3, 17),
        todate=dt.datetime(2023, 6, 1),
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
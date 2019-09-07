import datetime
import math
import os
import pandas as pd
from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer import FigureDrawer
from models.mathematics import range_2nd_decimal


class Trader():
    TIME_STRING_FMT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, operation='verification'):
        if operation in ['verification']:
            inst = OandaPyClient.select_instrument()
            self.__instrument = inst['name']
            self.__static_spread = inst['spread']
        else:
            self.__instrument = os.environ.get('INSTRUMENT') or 'USD_JPY'
            self.__static_spread = 0.0

        self._operation = operation
        self._client = OandaPyClient(instrument=self.get_instrument())
        self.__ana = Analyzer()
        self.__drawer = FigureDrawer()
        self.__columns = ['sequence', 'price', 'stoploss', 'type', 'time', 'profit']
        self.__granularity = os.environ.get('GRANULARITY') or 'M5'
        sl_buffer = round(float(os.environ.get('STOPLOSS_BUFFER')), 2)
        self._STOPLOSS_BUFFER_pips = sl_buffer or 0.05
        self._position = None

        if operation == 'verification':
            self.__request_custom_candles()
        elif operation == 'live':
            result = self._client.request_is_tradeable()
            self.tradeable = result['tradeable']
            if not self.tradeable:
                self._log_skip_reason('1. market is not open')
                self.__drawer.close_all()
                return
            self._client.load_specified_length_candles(granularity=self.__granularity)
        else:
            return

        # OPTIMIZE: これがあるせいで意外とトレードが発生しない
        self._client.request_current_price()

        result = self.__ana.calc_indicators()
        if 'error' in result:
            self._log_skip_reason(result['error'])
            return
        elif operation != 'live':
            print(result['success'])

        self._indicators = self.__ana.get_indicators()
        self.__initialize_position_variables()

    def __initialize_position_variables(self):
        self.__set_position({'type': 'none'})
        self.__hist_positions = {'long': [], 'short': []}

    def __set_position(self, position_dict):
        self._position = position_dict

    #
    # public
    #
    def get_instrument(self):
        return self.__instrument

    def auto_verify_trading_rule(self, accurize=True):
        ''' tradeルールを自動検証 '''
        print(self.__demo_swing_trade()['success'])
        if accurize and (self.__granularity[0] != 'M'):
            print(self.__accurize_entry_prices()['success'])

    def verify_varios_stoploss(self, accurize=True):
        ''' StopLossの設定値を自動でスライドさせて損益を検証 '''
        verification_dataframes_array = []
        stoploss_buffer_list = range_2nd_decimal(0.01, 0.10, 0.02)
        stoploss_buffer_list.append(0.50)

        for stoploss_buf in stoploss_buffer_list:
            print('[Trader] stoploss buffer: {}pipsで検証開始...'.format(stoploss_buf))
            self._STOPLOSS_BUFFER_pips = stoploss_buf
            self.auto_verify_trading_rule(accurize=accurize)

            self.__calc_statistics()
            _df = pd.concat(
                [
                    pd.DataFrame(self.__hist_positions['long'], columns=self.__columns),
                    pd.DataFrame(self.__hist_positions['short'], columns=self.__columns)
                ],
                axis=1, keys=['long', 'short'],
                names=['type', '-']
            )
            verification_dataframes_array.append(_df)

        result = pd.concat(
            verification_dataframes_array,
            axis=1, keys=stoploss_buffer_list,
            names=['SL_buffer']
        )
        result.to_csv('./tmp/sl_verify_{inst}.csv'.format(inst=self.get_instrument()))

    def draw_chart(self):
        ''' チャートや指標をpngに描画 '''
        MAX_ROWS = 200
        drwr = self.__drawer
        df_pos = {
            'long': pd.DataFrame(self.__hist_positions['long'], columns=self.__columns),
            'short': pd.DataFrame(self.__hist_positions['short'], columns=self.__columns)
        }

        df_len = len(self._indicators)
        dfs_indicator = self.__split_df_by_200rows(self._indicators)
        dfs_long_hist = self.__split_df_by_200sequences(df_pos['long'], df_len)
        dfs_short_hist = self.__split_df_by_200sequences(df_pos['short'], df_len)

        df_segments_count = len(dfs_indicator)
        for i in range(0, df_segments_count):
            drwr.draw_indicators(d_frame=dfs_indicator[i])

            start = df_len - MAX_ROWS * (i + 1)
            if start < 0: start = 0
            end = df_len - MAX_ROWS * i
            sr_time = drwr.draw_candles(start, end)['time']

            long_entry_df = dfs_long_hist[i][dfs_long_hist[i].type == 'long']
            long_trail_df = dfs_long_hist[i][dfs_long_hist[i].type == 'trail']
            long_close_df = dfs_long_hist[i][dfs_long_hist[i].type == 'close']
            short_entry_df = dfs_short_hist[i][dfs_short_hist[i].type == 'short']
            short_trail_df = dfs_short_hist[i][dfs_short_hist[i].type == 'trail']
            short_close_df = dfs_short_hist[i][dfs_short_hist[i].type == 'close']

            drwr.draw_positions_df(positions_df=long_entry_df, plot_type=drwr.PLOT_TYPE['long'])
            drwr.draw_positions_df(positions_df=long_trail_df, plot_type=drwr.PLOT_TYPE['trail'])
            drwr.draw_positions_df(positions_df=long_close_df, plot_type=drwr.PLOT_TYPE['exit'])
            drwr.draw_positions_df(positions_df=short_entry_df, plot_type=drwr.PLOT_TYPE['short'])
            drwr.draw_positions_df(positions_df=short_trail_df, plot_type=drwr.PLOT_TYPE['trail'], nolabel='_nolegend_')
            drwr.draw_positions_df(positions_df=short_close_df, plot_type=drwr.PLOT_TYPE['exit'],  nolabel='_nolegend_')
            result = drwr.create_png(
                instrument=self.get_instrument(),
                granularity=self.__granularity,
                sr_time=sr_time, num=i
            )

            drwr.close_all()
            if df_segments_count != i + 1:
                drwr.init_figure()
            if 'success' in result:
                print(result['success'], '/{}'.format(df_segments_count))

        return {
            'success': '[Trader] チャート分析、png生成完了',
            # メール送信フラグ: 今は必要ない
            'alart_necessary': False
        }

    def report_trading_result(self):
        ''' ポジション履歴をcsv出力 '''
        self.__calc_statistics()

        df_long = pd.DataFrame.from_dict(self.__hist_positions['long'])
        df_short = pd.DataFrame.from_dict(self.__hist_positions['short'])
        df_long.to_csv('./tmp/long_history.csv')
        df_short.to_csv('./tmp/short_history.csv')

        print('[Trader] ポジション履歴をcsv出力完了')

    #
    # Shared with subclass
    #

    def _SMA_run_along_trend(self, index, trend):
        sma = self._indicators['20SMA']
        if trend == 'bull' and sma[index - 1] < sma[index]:
            return True
        elif trend == 'bear' and sma[index - 1] > sma[index]:
            return True

        if self._operation == 'live':
            print('[Trader] Trend: {}, 20SMA: {} -> {}'.format(trend, sma[index - 1], sma[index]))
            self._log_skip_reason('c. 20SMA not run along trend')
        return False

    def _over_2_sigma(self, index, o_price):
        if self._indicators['band_+2σ'][index] < o_price or \
           self._indicators['band_-2σ'][index] > o_price:
            if self._operation == 'live':
                self._log_skip_reason(
                    'c. {}: o_price is over 2sigma'.format(FXBase.get_candles().time[index])
                )
            return True

        return False

    def _expand_MA_gap(self, index, trend):
        sma = self._indicators['20SMA']
        ema = self._indicators['10EMA']

        previous_gap = ema[index - 1] - sma[index - 1]
        current_gap = ema[index] - sma[index]

        if trend == 'bull':
            ma_gap_is_expanding = previous_gap < current_gap
        elif trend == 'bear':
            ma_gap_is_expanding = previous_gap > current_gap

        if not ma_gap_is_expanding and self._operation == 'live':
            self._log_skip_reason(
                'c. {}: MA_gap is shrinking'.format(FXBase.get_candles().time[index])
            )
        return ma_gap_is_expanding

    def _check_trend(self, index, c_price):
        '''
        ルールに基づいてトレンドの有無を判定
        '''
        sma = self._indicators['20SMA'][index]
        ema = self._indicators['10EMA'][index]
        parabo = self._indicators['SAR'][index]
        if sma < ema < c_price and parabo < c_price:
            trend = 'bull'
        elif sma > ema > c_price and parabo > c_price:
            trend = 'bear'
        else:
            trend = None
            if self._operation == 'live':
                print('[Trader] 20SMA: {}, 10EMA: {}, close: {}'.format(sma, ema, c_price))
                self._log_skip_reason('2. There isn`t the trend')
        return trend

    def _stochastic_allow_trade(self, index, trend):
        ''' stocがtrendと一致した動きをしていれば true を返す '''
        stod = self._indicators['stoD:3'][index]
        stosd = self._indicators['stoSD:3'][index]
        result = False

        if trend == 'bull' and (stod > stosd or stod > 80):
            result = True
        elif trend == 'bear' and (stod < stosd or stod < 20):
            result = True

        if result is False and self._operation == 'live':
            print('[Trader] stoD: {}, stoSD: {}'.format(stod, stosd))
            self._log_skip_reason('c. stochastic denies trade')
        return result

    def _find_thrust(self, i, trend):
        '''
        thrust発生の有無と方向を判定して返却する
        '''
        candles = FXBase.get_candles()
        candles_h = candles.high
        candles_l = candles.low
        if trend == 'bull' and candles_h[i] > candles_h[i - 1]:
            direction = 'long'
        elif trend == 'bear' and candles_l[i] < candles_l[i - 1]:
            direction = 'short'
        else:
            direction = None
            if self._operation == 'live':
                print('[Trader] Trend: {}, high-1: {}, high: {}, low-1: {}, low: {}'.format(
                    trend, candles_h[i - 1], candles_h[i], candles_l[i - 1], candles_l[i]
                ))
                self._log_skip_reason('3. There isn`t thrust')
        return direction

    def _judge_settle_position(self, i, c_price):
        candles = FXBase.get_candles()
        parabolic = self._indicators['SAR']
        position_type = self._position['type']
        stoploss_price = self._position['stoploss']
        if position_type == 'long':
            possible_stoploss = candles.low[i - 1] - self._STOPLOSS_BUFFER_pips
            if possible_stoploss > stoploss_price:
                stoploss_price = possible_stoploss
                self._trail_stoploss(
                    new_stop=stoploss_price, time=candles.time[i]
                )
            # INFO: 本番ではstoplossで決済されるので不要
            if operation != 'live' and stoploss_price > candles.low[i] - self.__static_spread:
                self._settle_position(
                    index=i, price=stoploss_price, time=candles.time[i]
                )
            elif parabolic[i] > c_price - self.__static_spread:
                self._settle_position(
                    index=i, price=parabolic[i], time=candles.time[i]
                )
        elif position_type == 'short':
            possible_stoploss = candles.high[i - 1] + self._STOPLOSS_BUFFER_pips
            if possible_stoploss < stoploss_price:
                stoploss_price = possible_stoploss
                self._trail_stoploss(
                    new_stop=stoploss_price, time=candles.time[i]
                )
            # INFO: 本番ではstoplossで決済されるので不要
            if operation != 'live' and stoploss_price < candles.high[i]:
                self._settle_position(
                    index=i, price=stoploss_price, time=candles.time[i]
                )
            elif parabolic[i] < c_price:
                self._settle_position(
                    index=i, price=parabolic[i], time=candles.time[i]
                )

    #
    # private
    #

    def __request_custom_candles(self):
        # Custom request
        print('何日分のデータを取得する？(半角数字): ', end='')
        days = int(input())
        if days > 365:
            print('[ALERT] 現在は365日までに制限しています')
            exit()

        print('取得スパンは？(ex: M5): ', end='')
        self.__granularity = str(input())

        result = self._client.load_long_chart(days=days, granularity=self.__granularity)
        if 'error' in result:
            print(result['error'])
            exit()
        FXBase.set_candles(result['candles'])

    def __demo_swing_trade(self):
        ''' スイングトレードのentry pointを検出 '''
        sma = self._indicators['20SMA']
        # INFO: 繰り返しデモする場合に前回のpositionが残っているので、リセットする
        self.__initialize_position_variables()

        close_candles = FXBase.get_candles().close
        candle_length = len(close_candles)
        for index, close_price in enumerate(close_candles):
            print('[Trader] progress... {i}/{total}'.format(i=index, total=candle_length))
            self._position['sequence'] = index
            if self._position['type'] == 'none':
                if math.isnan(sma[index]):
                    continue
                trend = self._check_trend(index, close_price)
                if trend is None:
                    continue

                if os.environ.get('CUSTOM_RULE') == 'on':
                    # INFO: 総損益減だが、勝率増、drawdown減、PF・RFが改善
                    if not self._SMA_run_along_trend(index, trend):
                        continue
                    # 大失敗を防いでくれる
                    if self._over_2_sigma(index, o_price=FXBase.get_candles().open[index]):
                        continue
                    # 大幅に改善する
                    if not self._expand_MA_gap(index, trend):
                        continue
                    # 若干効果あり
                    if not self._stochastic_allow_trade(index, trend):
                        continue

                direction = self._find_thrust(index, trend)
                if direction is None:
                    continue

                self._create_position(index, direction)
            else:
                self._judge_settle_position(index, close_price)

        return {'success': '[Trader] 売買判定終了'}

    def _create_position(self, index, direction):
        '''
        ルールに基づいてポジションをとる(検証用)
        '''
        candles = FXBase.get_candles()
        highs = candles.high
        lows = candles.low
        if direction == 'long':
            # INFO: 窓開けを想定して max, min を使用（動作検証中）
            entry_price = max(highs[index - 1], candles.open[index])
            stoploss = lows[index - 1] - self._STOPLOSS_BUFFER_pips
        elif direction == 'short':
            entry_price = min(lows[index - 1], candles.open[index]) - self.__static_spread
            stoploss = highs[index - 1] + self._STOPLOSS_BUFFER_pips

        self.__set_position({
            'sequence': index, 'price': entry_price, 'stoploss': stoploss,
            'type': direction, 'time': candles.time[index]
        })
        self.__hist_positions[direction].append(self._position.copy())

    def _trail_stoploss(self, new_stop, time):
        direction = self._position['type']
        self._position['stoploss'] = new_stop
        position_after_trailing = self._position.copy()
        position_after_trailing['type'] = 'trail'
        position_after_trailing['time'] = time
        self.__hist_positions[direction].append(position_after_trailing)

    def _settle_position(self, index, price, time):
        '''
        ポジション解消の履歴を残す

        Parameters
        ----------
        index : int
            ポジションを解消するタイミングを表す
        price : float
            ポジション解消時の価格
        time : string
            ポジションを解消する日（時）

        Returns
        -------
        None
        '''
        direction = self._position['type']
        self.__set_position({'type': 'none'})
        self.__hist_positions[direction].append({
            'sequence': index, 'price': price,
            'stoploss': 0.0, 'type': 'close', 'time': time
        })

    def _log_skip_reason(self, reason):
        print('[Trader] skip: {}'.format(reason))
        print('[Trader] -------- end --------')

    def __accurize_entry_prices(self):
        '''
        ポジション履歴のエントリーpriceを、実際にエントリー可能な価格に修正する
        '''
        first_time = self.__str_to_datetime(FXBase.get_candles().iloc[0, :].time[:19])
        last_time = self.__str_to_datetime(FXBase.get_candles().iloc[-1, :].time[:19])
        _m10_candles = self._client.load_or_query_candles(first_time, last_time, granularity='M10')

        # long価格の修正
        len_of_long_hist = len(self.__hist_positions['long']) - 1
        for i, row in enumerate(self.__hist_positions['long']):
            if i == len_of_long_hist:
                break

            print('[Trader] long-accurize: {i}/{total}'.format(i=i, total=len_of_long_hist))
            if row['type'] == 'long':
                start = row['time'][:19]
                end = self.__add_candle_duration(row['time'][:19])
                short_candles = _m10_candles.loc[start:end, :]

                # TODO: dataframeでなく辞書をloopさせればもっと早くなる
                for _j, m10_row in short_candles.iterrows():
                    if row['price'] < m10_row.high:
                        old_price = row['price']
                        row['price'] = m10_row.high
                        row['time'] = m10_row.name
                        self.__chain_accurization(
                            i, 'long', old_price, accurater_price=m10_row.high
                        )
                        break

        # short価格の修正
        len_of_short_hist = len(self.__hist_positions['short']) - 1
        for i, row in enumerate(self.__hist_positions['short']):
            if i == len_of_short_hist:
                break

            print('[Trader] short-accurize: {i}/{total}'.format(i=i, total=len_of_short_hist))
            if row['type'] == 'short':
                start = row['time'][:19]
                end = self.__add_candle_duration(row['time'][:19])
                short_candles = _m10_candles.loc[start:end, :]

                for _j, m10_row in short_candles.iterrows():
                    if row['price'] > m10_row.low:
                        old_price = row['price']
                        row['price'] = m10_row.low
                        row['time'] = m10_row.name
                        self.__chain_accurization(
                            i, 'short', old_price, accurater_price=m10_row.low
                        )
                        break

        return {'success': '[Trader] entry価格を、現実的に取引可能な値に修正'}

    def __add_candle_duration(self, start_string):
        start_time = self.__str_to_datetime(start_string)
        granularity = self.__granularity
        time_unit = granularity[0]
        if time_unit == 'M':
            candle_duration = datetime.timedelta(minutes=int(granularity[1:]))
        elif time_unit == 'H':
            candle_duration = datetime.timedelta(hours=int(granularity[1:]))
        elif time_unit == 'D':
            candle_duration = datetime.timedelta(days=1)

        a_minute = datetime.timedelta(minutes=1)
        result = (start_time + candle_duration - a_minute).strftime(Trader.TIME_STRING_FMT)
        return result

    def __chain_accurization(self, index, entry_type, old_price, accurater_price):
        index += 1
        length = len(self.__hist_positions[entry_type])
        while index < length:
            if self.__hist_positions[entry_type][index]['price'] != old_price:
                break

            self.__hist_positions[entry_type][index]['price'] = accurater_price
            index += 1

    def __str_to_datetime(self, time_string):
        result_dt = datetime.datetime.strptime(time_string, Trader.TIME_STRING_FMT)
        return result_dt

    def __split_df_by_200rows(self, d_frame):
        dfs = []
        MAX_LEN = 200
        df_len = len(d_frame)
        loop = 0

        while MAX_LEN * loop < df_len:
            end = df_len - MAX_LEN * loop
            loop += 1
            start = df_len - MAX_LEN * loop
            start = start if start > 0 else 0
            dfs.append(d_frame[start:end].reset_index(drop=True))
        return dfs

    def __split_df_by_200sequences(self, d_frame, df_len):
        dfs = []
        MAX_LEN = 200
        loop = 0

        while MAX_LEN * loop < df_len:
            end = df_len - MAX_LEN * loop
            loop += 1
            start = df_len - MAX_LEN * loop
            start = start if start > 0 else 0
            df_target = d_frame[(start <= d_frame.sequence) & (d_frame.sequence < end)].copy()
            # 描画は sequence に基づいて行われるので、ずらしておく
            df_target['sequence'] = df_target.sequence - start
            dfs.append(df_target)
        return dfs

    def __calc_statistics(self):
        ''' トレード履歴の統計情報計算処理を呼び出す '''
        long_entry_array = self.__hist_positions['long']
        long_entry_array = self.__calc_profit(long_entry_array, sign=1)
        short_entry_array = self.__hist_positions['short']
        short_entry_array = self.__calc_profit(short_entry_array, sign=-1)

        result = self.__calc_detaild_statistics(long_entry_array, short_entry_array)
        candles = FXBase.get_candles()

        duration = '{start} ~ {end}'.format(
            start=candles.time[20],
            end=candles.time.tail(1).values[0]
        )
        columns = [
            'Duration', 'CandlesCnt', 'EntryCnt', 'Spread', 'WinRate', 'WinCnt', 'LoseCnt',
            'Gross', 'GrossProfit', 'GrossLoss', 'MaxProfit', 'MaxLoss',
            'MaxDrawdown', 'Profit Factor', 'Recovery Factor'
        ]
        result_row = [
            duration,                # 'Duration'
            len(candles) - 20,       # 'CandlesCnt'
            result['trades_count'],  # 'EntryCnt'
            self.__static_spread,    # 'Spread'
            result['win_rate'],      # 'WinRate'
            result['win_count'],     # 'WinCnt'
            result['lose_count'],    # 'LoseCnt'
            round(result['profit_sum'] * 100, 3),    # 'Gross'
            round(result['gross_profit'] * 100, 3),  # 'GrossProfit'
            round(result['gross_loss'] * 100, 3),    # 'GrossLoss'
            round(result['max_profit'] * 100, 3),    # 'MaxProfit'
            round(result['max_loss'] * 100, 3),      # 'MaxLoss'
            round(result['drawdown'] * 100, 3),      # 'MaxDrawdown'
            result['profit_factor'],                 # 'Profit Factor'
            result['recovery_factor']                # 'Recovery Factor'
        ]
        result_df = pd.DataFrame([result_row], columns=columns)
        result_df.to_csv('tmp/verify_results.csv', encoding='shift-jis', mode='a', index=False, header=False)

    def __calc_profit(self, entry_array, sign=1):
        ''' トレード履歴の利益を計算 '''
        gross = 0
        gross_max = 0
        # INFO: pandas-dataframe化して計算するよりも速度が圧倒的に早い
        for i, row in enumerate(entry_array):
            if row['type'] == 'close':
                row['profit'] = sign * (row['price'] - entry_array[i - 1]['price'])
                gross += row['profit']
                gross_max = max(gross_max, gross)
            row['gross'] = gross
            row['drawdown'] = gross - gross_max
        return entry_array

    def __calc_detaild_statistics(self, long_entry_array, short_entry_array):
        ''' トレード履歴の詳細な分析を行う '''
        long_count = len([row['type'] for row in long_entry_array if row['type'] == 'long'])
        short_count = len([row['type'] for row in short_entry_array if row['type'] == 'short'])

        long_profit_array = \
            [row['profit'] for row in long_entry_array if row['type'] == 'close']
        short_profit_array = \
            [row['profit'] for row in short_entry_array if row['type'] == 'close']

        profit_array \
            = [profit for profit in long_profit_array if profit > 0] \
            + [profit for profit in short_profit_array if profit > 0]
        loss_array \
            = [profit for profit in long_profit_array if profit < 0] \
            + [profit for profit in short_profit_array if profit < 0]

        max_drawdown = min([row['drawdown'] for row in (long_entry_array + short_entry_array)])
        gross_profit = sum(profit_array)
        gross_loss = sum(loss_array)

        return {
            'trades_count': long_count + short_count,
            'win_rate': round(len(profit_array) / (long_count + short_count) * 100, 2),
            'win_count': len(profit_array),
            'lose_count': len(loss_array),
            'long_count': long_count,
            'short_count': short_count,
            'profit_sum': sum(long_profit_array + short_profit_array),
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'max_profit': max(profit_array),
            'max_loss': min(loss_array),
            'drawdown': max_drawdown,
            'profit_factor': round(-gross_profit / gross_loss, 2),
            'recovery_factor': round((gross_profit + gross_loss) / -max_drawdown, 2)
        }


class RealTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='verification'):
        super(RealTrader, self).__init__(operation=operation)

    #
    # Public
    #
    def apply_trading_rule(self):
        self.__play_swing_trade()

    #
    # Override shared methods
    #
    def _create_position(self, index, direction):
        '''
        ルールに基づいてポジションをとる(Oanda通信有)
        '''
        candles = FXBase.get_candles()
        if direction == 'long':
            sign = ''
            stoploss = candles.low[index - 1] - self._STOPLOSS_BUFFER_pips
        elif direction == 'short':
            sign = '-'
            stoploss = candles.high[index - 1] + self._STOPLOSS_BUFFER_pips
        self._client.request_market_ordering(posi_nega_sign=sign, stoploss_price=stoploss)

    def _trail_stoploss(self, new_stop, time):
        '''
        ポジションのstoploss-priceを強気方向へ修正する
        Parameters
        ----------
        new_stop : float
            新しいstoploss-price
        time : string
            不要

        Returns
        -------
        None
        '''
        result = self._client.request_trailing_stoploss(stoploss_price=new_stop)
        print(result)

    def _settle_position(self, index, price, time):
        '''
        ポジションをcloseする

        Parameters
        ----------
        index : int
        price : float
        time : string
            全て不要

        Returns
        -------
        None
        '''
        from pprint import pprint
        pprint(self._client.request_closing_position())

    #
    # Private
    #
    def __play_swing_trade(self):
        ''' 現在のレートにおいて、スイングトレードルールでトレード '''
        print('[Trader] -------- start --------')
        last_index = len(self._indicators) - 1
        close_price = FXBase.get_candles().close.values[-1]

        self.__set_position(self.__load_position())
        if self._position['type'] == 'none':
            trend = self._check_trend(index=last_index, c_price=close_price)
            if trend is None:
                return

            if os.environ.get('CUSTOM_RULE') == 'on':
                if not self._SMA_run_along_trend(last_index, trend):
                    return
                if self._over_2_sigma(last_index, o_price=FXBase.get_candles().open[last_index]):
                    return
                if not self._expand_MA_gap(last_index, trend):
                    return
                if not self._stochastic_allow_trade(last_index, trend):
                    return

            direction = self._find_thrust(last_index, trend)
            if direction is None:
                return

            self._create_position(last_index, direction)
        else:
            self._judge_settle_position(last_index, close_price)

        return None

    def __load_position(self):
        pos = {'type': 'none'}
        open_trades = self._client.request_open_trades()
        if open_trades == []:
            return pos

        # Open position の情報抽出
        target = open_trades[0]
        pos['price'] = float(target['price'])
        if target['currentUnits'][0] == '-':
            pos['type'] = 'short'
        else:
            pos['type'] = 'long'
        if 'stopLossOrder' not in target:
            return pos

        pos['stoploss'] = float(target['stopLossOrder']['price'])
        return pos

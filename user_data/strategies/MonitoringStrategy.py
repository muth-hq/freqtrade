import logging
import requests
import pandas as pd
from datetime import datetime
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair
from pandas import DataFrame
import talib.abstract as ta
import pandas_ta as pta

logger = logging.getLogger(__name__)

class MonitoringStrategy(IStrategy):
    """
    Dynamic MonitoringStrategy for portfolio monitoring
    Monitors 6 portfolio coins with various technical indicators
    Sends signals via webhook to backend
    """
    # Strategy interface version
    INTERFACE_VERSION = 3
    
    # Portfolio coins to monitor
    PORTFOLIO_COINS = [
        "BTC/USDT",
        "ETH/USDT", 
        "ADA/USDT",
        "DOT/USDT",
        "LINK/USDT",
        "MATIC/USDT"
    ]
    
    # Webhook configuration
    WEBHOOK_URL = "http://localhost:3001/api/freqtrade-signals"
    
    # Strategy parameters
    timeframe = '5m'
    
    # ROI table (not used for monitoring)
    minimal_roi = {
        "0": 10
    }
    
    # Stoploss (not used for monitoring)
    stoploss = -0.99
    
    # Trailing stop (not used for monitoring)
    trailing_stop = False
    
    # No trading - monitoring only
    process_only_new_candles = True
    use_exit_signal = False
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Store last signal timestamps to avoid spam
        self.last_signals = {}
    
    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        """
        pairs = []
        for coin in self.PORTFOLIO_COINS:
            pairs.append((coin, self.timeframe))
        return pairs
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        pair = metadata['pair']
        
        if pair not in self.PORTFOLIO_COINS:
            return dataframe
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_upper'] = bollinger['upperband']
        
        # Moving Averages
        dataframe['ma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['ma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['ema_12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        
        # Stochastic Oscillator
        stoch = ta.STOCH(dataframe)
        dataframe['stoch_k'] = stoch['slowk']
        dataframe['stoch_d'] = stoch['slowd']
        
        # Williams %R
        dataframe['williams_r'] = ta.WILLR(dataframe, timeperiod=14)
        
        # ADX (Average Directional Index)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        This strategy is monitoring-only, so we don't actually enter trades
        """
        pair = metadata['pair']
        
        if pair not in self.PORTFOLIO_COINS:
            dataframe['enter_long'] = 0
            return dataframe
        
        # Check for various signals and send webhooks
        self._check_and_send_signals(dataframe, pair)
        
        # Never actually enter trades - monitoring only
        dataframe['enter_long'] = 0
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        This strategy is monitoring-only
        """
        dataframe['exit_long'] = 0
        return dataframe
    
    def _check_and_send_signals(self, dataframe: DataFrame, pair: str):
        """
        Check for various technical analysis signals and send webhooks
        """
        if len(dataframe) < 50:  # Need more data for proper indicator calculation
            logger.debug(f"Not enough data for {pair}: {len(dataframe)} rows")
            return
        
        try:
            current = dataframe.iloc[-1]
            previous = dataframe.iloc[-2]
            
            # Log current indicator values for debugging
            logger.debug(f"[{pair}] RSI: {current.get('rsi', 'N/A')}, MACD: {current.get('macd', 'N/A')}, ADX: {current.get('adx', 'N/A')}")
            
            signals = []
        except Exception as e:
            logger.error(f"Error accessing dataframe data for {pair}: {str(e)}")
            return
        
        # RSI Signals - check for valid RSI values
        if not pd.isna(current['rsi']):
            if current['rsi'] < 30:
                signals.append({
                    'type': 'rsi_oversold',
                    'message': f'{pair} RSI oversold: {current["rsi"]:.2f}',
                    'value': float(current['rsi']),
                    'strength': 'high' if current['rsi'] < 25 else 'medium'
                })
            elif current['rsi'] > 70:
                signals.append({
                    'type': 'rsi_overbought', 
                    'message': f'{pair} RSI overbought: {current["rsi"]:.2f}',
                    'value': float(current['rsi']),
                    'strength': 'high' if current['rsi'] > 75 else 'medium'
                })
        
        # Golden Cross / Death Cross - check for valid MA values
        if (not pd.isna(current['ma_20']) and not pd.isna(current['ma_50']) and 
            not pd.isna(previous['ma_20']) and not pd.isna(previous['ma_50'])):
            if previous['ma_20'] <= previous['ma_50'] and current['ma_20'] > current['ma_50']:
                signals.append({
                    'type': 'golden_cross',
                    'message': f'{pair} Golden Cross: MA20 crossed above MA50',
                    'value': {'ma_20': float(current['ma_20']), 'ma_50': float(current['ma_50'])},
                    'strength': 'high'
                })
            elif previous['ma_20'] >= previous['ma_50'] and current['ma_20'] < current['ma_50']:
                signals.append({
                    'type': 'death_cross',
                    'message': f'{pair} Death Cross: MA20 crossed below MA50',
                    'value': {'ma_20': float(current['ma_20']), 'ma_50': float(current['ma_50'])},
                    'strength': 'high'
                })
        
        # MACD Signals - check for valid MACD values
        if (not pd.isna(current['macd']) and not pd.isna(current['macdsignal']) and 
            not pd.isna(previous['macd']) and not pd.isna(previous['macdsignal'])):
            if previous['macd'] <= previous['macdsignal'] and current['macd'] > current['macdsignal']:
                signals.append({
                    'type': 'macd_bullish',
                    'message': f'{pair} MACD bullish crossover',
                    'value': {'macd': float(current['macd']), 'signal': float(current['macdsignal'])},
                    'strength': 'medium'
                })
            elif previous['macd'] >= previous['macdsignal'] and current['macd'] < current['macdsignal']:
                signals.append({
                    'type': 'macd_bearish',
                    'message': f'{pair} MACD bearish crossover', 
                    'value': {'macd': float(current['macd']), 'signal': float(current['macdsignal'])},
                    'strength': 'medium'
                })
        
        # Volume Spike Detection - check for valid volume values
        if (not pd.isna(current['volume']) and not pd.isna(current['volume_sma']) and 
            current['volume_sma'] > 0 and current['volume'] > current['volume_sma'] * 2):
            signals.append({
                'type': 'volume_spike',
                'message': f'{pair} Volume spike detected: {current["volume"]:.0f} vs avg {current["volume_sma"]:.0f}',
                'value': {'volume': float(current['volume']), 'avg_volume': float(current['volume_sma'])},
                'strength': 'medium'
            })
        
        # Bollinger Band Breakouts - check for valid BB values
        if (not pd.isna(current['close']) and not pd.isna(current['bb_upper']) and not pd.isna(current['bb_lower'])):
            if current['close'] > current['bb_upper']:
                signals.append({
                    'type': 'bb_upper_breakout',
                    'message': f'{pair} Price broke above upper Bollinger Band',
                    'value': {'price': float(current['close']), 'bb_upper': float(current['bb_upper'])},
                    'strength': 'medium'
                })
            elif current['close'] < current['bb_lower']:
                signals.append({
                    'type': 'bb_lower_breakout',
                    'message': f'{pair} Price broke below lower Bollinger Band',
                    'value': {'price': float(current['close']), 'bb_lower': float(current['bb_lower'])},
                    'strength': 'medium'
                })
        
        # Stochastic Signals - check for valid stochastic values
        if (not pd.isna(current['stoch_k']) and not pd.isna(current['stoch_d'])):
            if current['stoch_k'] < 20 and current['stoch_d'] < 20:
                signals.append({
                    'type': 'stochastic_oversold',
                    'message': f'{pair} Stochastic oversold: K={current["stoch_k"]:.2f}, D={current["stoch_d"]:.2f}',
                    'value': {'stoch_k': float(current['stoch_k']), 'stoch_d': float(current['stoch_d'])},
                    'strength': 'medium'
                })
            elif current['stoch_k'] > 80 and current['stoch_d'] > 80:
                signals.append({
                    'type': 'stochastic_overbought',
                    'message': f'{pair} Stochastic overbought: K={current["stoch_k"]:.2f}, D={current["stoch_d"]:.2f}',
                    'value': {'stoch_k': float(current['stoch_k']), 'stoch_d': float(current['stoch_d'])},
                    'strength': 'medium'
                })
        
        # Williams %R Signals - check for valid Williams %R values
        if not pd.isna(current['williams_r']):
            if current['williams_r'] < -80:
                signals.append({
                    'type': 'williams_oversold',
                    'message': f'{pair} Williams %R oversold: {current["williams_r"]:.2f}',
                    'value': float(current['williams_r']),
                    'strength': 'low'
                })
            elif current['williams_r'] > -20:
                signals.append({
                    'type': 'williams_overbought',
                    'message': f'{pair} Williams %R overbought: {current["williams_r"]:.2f}',
                    'value': float(current['williams_r']),
                    'strength': 'low'
                })
        
        # ADX Trend Strength - check for valid ADX values
        if not pd.isna(current['adx']) and current['adx'] > 25:
            signals.append({
                'type': 'strong_trend',
                'message': f'{pair} Strong trend detected: ADX={current["adx"]:.2f}',
                'value': float(current['adx']),
                'strength': 'low'
            })
        
            # Send signals to webhook
            for signal in signals:
                self._send_webhook(pair, signal)
                
        except Exception as e:
            logger.error(f"Error processing signals for {pair}: {str(e)}")
            return
    
    def _send_webhook(self, pair: str, signal: dict):
        """
        Send signal data to webhook endpoint
        """
        signal_key = f"{pair}_{signal['type']}"
        current_time = datetime.now()
        
        # Rate limiting: don't send same signal type for same pair within 5 minutes
        if signal_key in self.last_signals:
            time_diff = (current_time - self.last_signals[signal_key]).total_seconds()
            if time_diff < 300:  # 5 minutes
                return
        
        payload = {
            'timestamp': current_time.isoformat(),
            'pair': pair,
            'signal_type': signal['type'],
            'message': signal['message'],
            'value': signal['value'],
            'strength': signal['strength'],
            'strategy': 'MonitoringStrategy'
        }
        
        try:
            response = requests.post(
                self.WEBHOOK_URL,
                json=payload,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook sent successfully for {pair}: {signal['type']}")
                self.last_signals[signal_key] = current_time
            else:
                logger.warning(f"Webhook failed for {pair}: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook request failed for {pair}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending webhook for {pair}: {str(e)}")
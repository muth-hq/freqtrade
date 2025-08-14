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
    
    # Webhook configuration - Updated for Trading Pipeline API
    WEBHOOK_URL = "http://172.20.0.1:8000/trpc/tradingPipeline.receiveFreqtradeSignal"
    
    # Test flag - set to True to generate test signals for API integration testing  
    # Set to False for real market indicator analysis
    TEST_MODE = True
    
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
        # Track portfolio-wide signals to avoid spam
        self.last_portfolio_signal = None
    
    def _extract_coin_symbol(self, pair: str) -> str:
        """Extract coin symbol from trading pair (e.g., BTC/USDT -> BTC)"""
        return pair.split('/')[0]
    
    def _get_portfolio_coins_list(self) -> list:
        """Get list of coin symbols for portfolio"""
        return [self._extract_coin_symbol(pair) for pair in self.PORTFOLIO_COINS]
    
    def _determine_macd_status(self, current: dict, previous: dict) -> str:
        """Determine MACD status based on current and previous values"""
        if pd.isna(current.get('macd')) or pd.isna(current.get('macdsignal')):
            return 'neutral'
        
        if pd.isna(previous.get('macd')) or pd.isna(previous.get('macdsignal')):
            return 'neutral'
            
        curr_macd = current['macd']
        curr_signal = current['macdsignal']
        prev_macd = previous['macd']
        prev_signal = previous['macdsignal']
        
        # Bullish crossover: MACD crosses above signal
        if prev_macd <= prev_signal and curr_macd > curr_signal:
            return 'bullish_crossover'
        # Bearish crossover: MACD crosses below signal  
        elif prev_macd >= prev_signal and curr_macd < curr_signal:
            return 'bearish_crossover'
        # Bearish divergence: MACD below signal line
        elif curr_macd < curr_signal:
            return 'bearish_divergence'
        else:
            return 'neutral'
    
    def _determine_bb_position(self, current: dict) -> str:
        """Determine Bollinger Band position"""
        if pd.isna(current.get('close')) or pd.isna(current.get('bb_upper')) or pd.isna(current.get('bb_lower')):
            return 'middle_band'
            
        price = current['close']
        bb_upper = current['bb_upper']
        bb_lower = current['bb_lower']
        bb_middle = current.get('bb_middle', (bb_upper + bb_lower) / 2)
        
        # Check for bounces off bands
        if price <= bb_lower * 1.001:  # Small tolerance for "at" the band
            return 'lower_band_bounce'
        elif price >= bb_upper * 0.999:  # Small tolerance for "at" the band
            return 'upper_band_bounce'
        # Check position relative to bands
        elif price > bb_upper:
            return 'upper_band'
        elif price < bb_lower:
            return 'lower_band'
        else:
            return 'middle_band'
    
    def _calculate_signal_strength(self, current: dict, signals: list) -> float:
        """Calculate overall signal strength from 0-1 based on indicators"""
        strength_score = 0.5  # Default neutral
        
        # RSI contribution
        if not pd.isna(current.get('rsi')):
            rsi = current['rsi']
            if rsi < 30:
                strength_score += 0.2  # Oversold = potential buy
            elif rsi > 70:
                strength_score += 0.1  # Overbought = potential sell signal
        
        # MACD contribution  
        macd_status = self._determine_macd_status(current, {})
        if 'bullish' in macd_status:
            strength_score += 0.15
        elif 'bearish' in macd_status:
            strength_score += 0.1
            
        # Volume contribution
        if not pd.isna(current.get('volume')) and not pd.isna(current.get('volume_sma')):
            if current['volume'] > current['volume_sma'] * 1.5:
                strength_score += 0.1
        
        # Number of signals contribution
        if len(signals) > 2:
            strength_score += 0.05
            
        return min(1.0, max(0.0, strength_score))

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
        Check for various technical analysis signals and send portfolio-wide webhook
        """
        if len(dataframe) < 50:  # Need more data for proper indicator calculation
            logger.debug(f"Not enough data for {pair}: {len(dataframe)} rows")
            return
        
        # Only process signals for the primary coin and send portfolio-wide snapshot
        # Rate limiting: only send portfolio signal once every 5 minutes
        current_time = datetime.now()
        if self.last_portfolio_signal:
            time_diff = (current_time - self.last_portfolio_signal).total_seconds()
            if time_diff < 300:  # 5 minutes
                logger.debug(f"Portfolio signal rate limited - last sent {time_diff:.1f}s ago")
                return
        
        try:
            current = dataframe.iloc[-1]
            previous = dataframe.iloc[-2]
            
            # Log current indicator values for debugging
            logger.debug(f"[{pair}] RSI: {current.get('rsi', 'N/A')}, MACD: {current.get('macd', 'N/A')}, ADX: {current.get('adx', 'N/A')}")
            
            # Extract coin symbol for portfolio snapshot
            coin = self._extract_coin_symbol(pair)
            
            # Build portfolio-wide signal matching our tRPC schema
            portfolio_signal = {
                'coin': coin,  # Primary coin that triggered the signal
                'indicators': {
                    'rsi': float(current.get('rsi', 50.0)) if not pd.isna(current.get('rsi')) else 50.0,
                    'macd': self._determine_macd_status(current, previous),
                    'bb_position': self._determine_bb_position(current),
                    'sma_20': float(current.get('ma_20', 0.0)) if not pd.isna(current.get('ma_20')) else None,
                    'sma_50': float(current.get('ma_50', 0.0)) if not pd.isna(current.get('ma_50')) else None,
                    'ema_12': float(current.get('ema_12', 0.0)) if not pd.isna(current.get('ema_12')) else None,
                    'ema_26': float(current.get('ema_26', 0.0)) if not pd.isna(current.get('ema_26')) else None,
                    'volume_24h': float(current.get('volume', 0.0)) if not pd.isna(current.get('volume')) else None,
                },
                'portfolio_coins': self._get_portfolio_coins_list(),
                'timestamp': current_time.isoformat() + 'Z',
                'signal_strength': self._calculate_signal_strength(current, []),
                'pair': pair,
                'timeframe': self.timeframe
            }
            
            # Send portfolio-wide snapshot
            self._send_portfolio_webhook(portfolio_signal)
            
        except Exception as e:
            logger.error(f"Error processing portfolio signal for {pair}: {str(e)}")
            return
    
    def _send_portfolio_webhook(self, portfolio_signal: dict):
        """
        Send portfolio-wide signal data to tRPC API endpoint
        """
        current_time = datetime.now()
        
        # Print portfolio signal for monitoring
        logger.info(f">>>>>>>>>>>>>> PORTFOLIO SIGNAL DETECTED: {portfolio_signal['coin']}")
        print(f">>>>>>>>>>>>>> PORTFOLIO SIGNAL DETECTED: {portfolio_signal['coin']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   📊 Primary Coin: {portfolio_signal['coin']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   📈 RSI: {portfolio_signal['indicators']['rsi']:.2f}", flush=True) 
        print(f">>>>>>>>>>>>>>>>   💪 MACD: {portfolio_signal['indicators']['macd']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   📋 BB Position: {portfolio_signal['indicators']['bb_position']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   🎯 Signal Strength: {portfolio_signal['signal_strength']:.2f}", flush=True)
        print(f">>>>>>>>>>>>>>>>   💼 Portfolio: {', '.join(portfolio_signal['portfolio_coins'])}", flush=True)
        print(f">>>>>>>>>>>>>>>>   ⏰ Time: {current_time.strftime('%H:%M:%S')}", flush=True)
        print(">>>>>>>>>>>>>> " + "-" * 50, flush=True)
        
        try:
            # Send to tRPC API endpoint
            response = requests.post(
                self.WEBHOOK_URL,
                json=portfolio_signal,  # Send the portfolio signal directly (matches our Zod schema)
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"Portfolio webhook sent successfully for {portfolio_signal['coin']}")
                print(f"✅ Portfolio webhook sent successfully!", flush=True)
                self.last_portfolio_signal = current_time
                
                # Parse and display response
                try:
                    response_data = response.json()
                    if response_data.get('success'):
                        execution_id = response_data['data']['execution_id']
                        print(f"🚀 Trading Pipeline triggered! Execution ID: {execution_id}", flush=True)
                    else:
                        print(f"⚠️  API response error: {response_data.get('error', 'Unknown error')}", flush=True)
                except:
                    print(f"✅ API responded successfully (couldn't parse response)", flush=True)
            else:
                logger.warning(f"Portfolio webhook failed: {response.status_code} - {response.text}")
                print(f"⚠️  Webhook failed: {response.status_code} - {response.text[:200]}", flush=True)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Portfolio webhook request failed: {str(e)}")
            print(f"⚠️  Webhook failed (connection error): {str(e)}", flush=True)
        except Exception as e:
            logger.error(f"Unexpected error sending portfolio webhook: {str(e)}")
            print(f"⚠️  Webhook error: {str(e)}", flush=True)
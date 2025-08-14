import logging
import requests
import pandas as pd
import random
from datetime import datetime
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair
from pandas import DataFrame
import talib.abstract as ta
import pandas_ta as pta

logger = logging.getLogger(__name__)

class MonitoringStrategyMock(IStrategy):
    """
    MOCK VERSION of Dynamic MonitoringStrategy for portfolio monitoring
    *** TEST_MODE = True *** - Generates predictable mock data for testing
    Monitors 6 portfolio coins with MOCK technical indicators
    Sends signals via webhook to backend
    
    IMPORTANT: This is the MOCK/TEST version for development and testing.
    Any logic changes here should be synced to the real MonitoringStrategy.py
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
    
    # *** MOCK MODE ALWAYS ENABLED ***
    TEST_MODE = True  # Always True for this mock version
    
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
        # Mock data generators
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data generators for consistent testing"""
        self.mock_cycles = 0
        self.mock_scenarios = [
            {
                'name': 'bullish_trend',
                'rsi_range': (35, 45),
                'macd': 'bullish_crossover',
                'bb_position': 'lower_band_bounce',
                'signal_strength': 0.75
            },
            {
                'name': 'bearish_trend', 
                'rsi_range': (65, 75),
                'macd': 'bearish_crossover',
                'bb_position': 'upper_band_bounce',
                'signal_strength': 0.65
            },
            {
                'name': 'neutral_market',
                'rsi_range': (45, 55),
                'macd': 'neutral',
                'bb_position': 'middle_band',
                'signal_strength': 0.50
            },
            {
                'name': 'oversold_bounce',
                'rsi_range': (25, 35),
                'macd': 'bullish_crossover',
                'bb_position': 'lower_band_bounce',
                'signal_strength': 0.85
            },
            {
                'name': 'overbought_correction',
                'rsi_range': (70, 80),
                'macd': 'bearish_divergence',
                'bb_position': 'upper_band',
                'signal_strength': 0.70
            }
        ]
    
    def _extract_coin_symbol(self, pair: str) -> str:
        """Extract coin symbol from trading pair (e.g., BTC/USDT -> BTC)"""
        return pair.split('/')[0]
    
    def _get_portfolio_coins_list(self) -> list:
        """Get list of coin symbols for portfolio"""
        return [self._extract_coin_symbol(pair) for pair in self.PORTFOLIO_COINS]
    
    def _generate_mock_indicators(self, coin: str) -> dict:
        """Generate realistic mock indicators for testing"""
        # Cycle through scenarios
        scenario = self.mock_scenarios[self.mock_cycles % len(self.mock_scenarios)]
        
        # Add some randomness but keep it predictable
        seed_value = hash(coin + str(self.mock_cycles)) % 1000
        random.seed(seed_value)
        
        # Generate mock RSI
        rsi_min, rsi_max = scenario['rsi_range']
        mock_rsi = random.uniform(rsi_min, rsi_max)
        
        # Generate mock price data
        base_prices = {
            'BTC': 45000,
            'ETH': 3000, 
            'ADA': 0.5,
            'DOT': 25,
            'LINK': 15,
            'MATIC': 1.2
        }
        base_price = base_prices.get(coin, 100)
        price_variation = random.uniform(0.95, 1.05)
        mock_price = base_price * price_variation
        
        # Generate mock moving averages
        sma_20 = mock_price * random.uniform(0.98, 1.02)
        sma_50 = mock_price * random.uniform(0.96, 1.04)
        ema_12 = mock_price * random.uniform(0.99, 1.01)
        ema_26 = mock_price * random.uniform(0.97, 1.03)
        
        # Generate mock volume (in millions)
        volume_multipliers = {
            'BTC': 25000000000,  # $25B
            'ETH': 15000000000,  # $15B
            'ADA': 500000000,    # $500M
            'DOT': 400000000,    # $400M
            'LINK': 600000000,   # $600M
            'MATIC': 300000000   # $300M
        }
        base_volume = volume_multipliers.get(coin, 100000000)
        mock_volume = base_volume * random.uniform(0.8, 1.5)
        
        return {
            'rsi': mock_rsi,
            'macd': scenario['macd'],
            'bb_position': scenario['bb_position'],
            'sma_20': sma_20,
            'sma_50': sma_50,
            'ema_12': ema_12,
            'ema_26': ema_26,
            'volume_24h': mock_volume,
            'signal_strength': scenario['signal_strength'],
            'scenario': scenario['name']
        }
    
    def _determine_macd_status(self, current: dict, previous: dict) -> str:
        """For mock mode, return predefined MACD status"""
        if self.TEST_MODE:
            # Return mock MACD status from scenario
            return getattr(self, '_current_mock_macd', 'neutral')
        
        # Real MACD logic (sync with MonitoringStrategy.py)
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
        """For mock mode, return predefined BB position"""
        if self.TEST_MODE:
            # Return mock BB position from scenario
            return getattr(self, '_current_mock_bb', 'middle_band')
        
        # Real BB logic (sync with MonitoringStrategy.py)
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
        """For mock mode, return predefined signal strength"""
        if self.TEST_MODE:
            # Return mock signal strength from scenario
            return getattr(self, '_current_mock_strength', 0.5)
        
        # Real signal strength logic (sync with MonitoringStrategy.py)
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
        In TEST_MODE: Adds mock indicators
        Otherwise: Adds real TA indicators (sync with MonitoringStrategy.py)
        """
        pair = metadata['pair']
        
        if pair not in self.PORTFOLIO_COINS:
            return dataframe
        
        if self.TEST_MODE:
            # Generate mock indicators for testing
            coin = self._extract_coin_symbol(pair)
            mock_data = self._generate_mock_indicators(coin)
            
            # Fill dataframe with mock values
            dataframe['rsi'] = mock_data['rsi']
            dataframe['macd'] = 0.1 if 'bullish' in mock_data['macd'] else -0.1
            dataframe['macdsignal'] = 0.05 if 'bullish' in mock_data['macd'] else -0.05
            dataframe['macdhist'] = 0.05
            dataframe['bb_lower'] = mock_data['sma_20'] * 0.98
            dataframe['bb_middle'] = mock_data['sma_20']
            dataframe['bb_upper'] = mock_data['sma_20'] * 1.02
            dataframe['ma_20'] = mock_data['sma_20']
            dataframe['ma_50'] = mock_data['sma_50']
            dataframe['ema_12'] = mock_data['ema_12']
            dataframe['ema_26'] = mock_data['ema_26']
            dataframe['volume'] = mock_data['volume_24h']
            dataframe['volume_sma'] = mock_data['volume_24h'] * 0.8
            
            # Store current mock values for signal processing
            self._current_mock_macd = mock_data['macd']
            self._current_mock_bb = mock_data['bb_position']
            self._current_mock_strength = mock_data['signal_strength']
            
            logger.info(f"🧪 MOCK DATA for {coin}: RSI={mock_data['rsi']:.1f}, MACD={mock_data['macd']}, BB={mock_data['bb_position']}, Scenario={mock_data['scenario']}")
            
        else:
            # Real indicator calculations (sync with MonitoringStrategy.py)
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
        *** INCLUDES MOCK DATA FUNCTIONALITY ***
        """
        if len(dataframe) < 50:  # Need more data for proper indicator calculation
            logger.debug(f"Not enough data for {pair}: {len(dataframe)} rows")
            return
        
        # Rate limiting: only send portfolio signal once every 30 seconds for testing
        current_time = datetime.now()
        if self.last_portfolio_signal:
            time_diff = (current_time - self.last_portfolio_signal).total_seconds()
            rate_limit = 30 if self.TEST_MODE else 300  # 30s for testing, 5min for real
            if time_diff < rate_limit:
                logger.debug(f"Portfolio signal rate limited - last sent {time_diff:.1f}s ago")
                return
        
        try:
            current = dataframe.iloc[-1]
            previous = dataframe.iloc[-2]
            
            # Log current indicator values for debugging
            logger.debug(f"[{pair}] RSI: {current.get('rsi', 'N/A')}, MACD: {current.get('macd', 'N/A')}, ADX: {current.get('adx', 'N/A')}")
            
            # Extract coin symbol for portfolio snapshot
            coin = self._extract_coin_symbol(pair)
            
            # In TEST_MODE, use mock data; otherwise use real data
            if self.TEST_MODE:
                mock_data = self._generate_mock_indicators(coin)
                self.mock_cycles += 1  # Advance to next scenario
                
                # Build portfolio-wide signal with MOCK data
                portfolio_signal = {
                    'coin': coin,  # Primary coin that triggered the signal
                    'indicators': {
                        'rsi': mock_data['rsi'],
                        'macd': mock_data['macd'],
                        'bb_position': mock_data['bb_position'],
                        'sma_20': mock_data['sma_20'],
                        'sma_50': mock_data['sma_50'],
                        'ema_12': mock_data['ema_12'],
                        'ema_26': mock_data['ema_26'],
                        'volume_24h': mock_data['volume_24h'],
                    },
                    'portfolio_coins': self._get_portfolio_coins_list(),
                    'timestamp': current_time.isoformat() + 'Z',
                    'signal_strength': mock_data['signal_strength'],
                    'pair': pair,
                    'timeframe': self.timeframe
                }
                
                logger.info(f"🧪 MOCK PORTFOLIO SIGNAL for {coin}: {mock_data['scenario']} scenario")
                
            else:
                # Build portfolio-wide signal with REAL data (sync with MonitoringStrategy.py)
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
        *** INCLUDES MOCK MODE LABELS ***
        """
        current_time = datetime.now()
        
        # Print portfolio signal for monitoring
        mode_label = "🧪 MOCK" if self.TEST_MODE else "📊 REAL"
        logger.info(f">>>>>>>>>>>>>> {mode_label} PORTFOLIO SIGNAL DETECTED: {portfolio_signal['coin']}")
        print(f">>>>>>>>>>>>>> {mode_label} PORTFOLIO SIGNAL DETECTED: {portfolio_signal['coin']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   📊 Primary Coin: {portfolio_signal['coin']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   📈 RSI: {portfolio_signal['indicators']['rsi']:.2f}", flush=True) 
        print(f">>>>>>>>>>>>>>>>   💪 MACD: {portfolio_signal['indicators']['macd']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   📋 BB Position: {portfolio_signal['indicators']['bb_position']}", flush=True)
        print(f">>>>>>>>>>>>>>>>   🎯 Signal Strength: {portfolio_signal['signal_strength']:.2f}", flush=True)
        print(f">>>>>>>>>>>>>>>>   💼 Portfolio: {', '.join(portfolio_signal['portfolio_coins'])}", flush=True)
        print(f">>>>>>>>>>>>>>>>   ⏰ Time: {current_time.strftime('%H:%M:%S')}", flush=True)
        if self.TEST_MODE:
            print(f">>>>>>>>>>>>>>>>   🧪 Mode: MOCK DATA for testing", flush=True)
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
                    if response_data.get('result', {}).get('data', {}).get('success'):
                        execution_id = response_data['result']['data']['data']['execution_id']
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
"""
TechnicalAnalyzer — RSI, MACD, Bollinger Bands, SMA, Momentum Signal 계산.
pandas + numpy 기반. 외부 API 불필요.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Union


class TechnicalAnalyzer:

    def compute_rsi(self, closes: List[float], period: int = 14) -> float:
        """RSI (0~100). 데이터 부족 시 50.0."""
        if len(closes) < period + 1:
            return 50.0
        arr = np.array(closes, dtype=float)
        deltas = np.diff(arr)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(float(100.0 - 100.0 / (1.0 + rs)), 2)

    def compute_macd(self, closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """MACD, Signal, Histogram. 데이터 부족 시 모두 0.0."""
        if len(closes) < slow + signal:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        s = pd.Series(closes, dtype=float)
        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            "macd": round(float(macd_line.iloc[-1]), 6),
            "signal": round(float(signal_line.iloc[-1]), 6),
            "histogram": round(float(histogram.iloc[-1]), 6),
        }

    def compute_bollinger_bands(self, closes: List[float], window: int = 20, num_std: float = 2.0) -> Dict[str, float]:
        """Bollinger Bands. upper/middle/lower/bandwidth/pct_b."""
        if len(closes) < window:
            mid = closes[-1] if closes else 0.0
            return {"upper": mid, "middle": mid, "lower": mid, "bandwidth": 0.0, "pct_b": 0.5}
        s = pd.Series(closes, dtype=float)
        middle = float(s.rolling(window=window).mean().iloc[-1])
        std = float(s.rolling(window=window).std().iloc[-1])
        upper = middle + num_std * std
        lower = middle - num_std * std
        bandwidth = (upper - lower) / (middle + 1e-8)
        pct_b = (closes[-1] - lower) / (upper - lower + 1e-8)
        return {
            "upper": round(upper, 4),
            "middle": round(middle, 4),
            "lower": round(lower, 4),
            "bandwidth": round(float(bandwidth), 4),
            "pct_b": round(float(np.clip(pct_b, 0.0, 1.0)), 4),
        }

    def compute_sma(self, closes: List[float], window: int) -> Optional[float]:
        """단순 이동평균. 데이터 부족 시 None."""
        if len(closes) < window:
            return None
        return round(float(np.mean(closes[-window:])), 4)

    def compute_momentum_signal(self, closes: List[float], rsi_period: int = 14) -> Dict[str, Union[str, float]]:
        """RSI + MACD 기반 종합 매매 시그널. signal: buy/sell/hold."""
        rsi = self.compute_rsi(closes, rsi_period)
        macd_data = self.compute_macd(closes)
        histogram = macd_data["histogram"]
        if rsi < 35 and histogram > 0:
            signal = "buy"
            strength = min((35 - rsi) / 35 * 0.5 + min(abs(histogram) * 100, 0.5), 1.0)
        elif rsi > 65 and histogram < 0:
            signal = "sell"
            strength = min((rsi - 65) / 35 * 0.5 + min(abs(histogram) * 100, 0.5), 1.0)
        else:
            signal = "hold"
            strength = 0.3
        return {
            "signal": signal,
            "rsi": rsi,
            "macd_histogram": round(histogram, 6),
            "strength": round(float(np.clip(strength, 0.0, 1.0)), 4),
        }

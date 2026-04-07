"""
SentimentAnalyzer — 키워드 기반 금융 감성 분석. 외부 API 불필요.
"""
import re
from typing import List, Dict

_POSITIVE = {
    "strong", "growth", "beat", "bullish", "rally", "surge", "outperform",
    "upgrade", "record", "expand", "recovery", "robust", "momentum", "gain",
    "profit", "revenue", "positive", "opportunity", "upside", "breakout",
    "acceleration", "improvement", "optimistic", "buy", "overweight",
}
_NEGATIVE = {
    "weak", "decline", "miss", "bearish", "selloff", "plunge", "underperform",
    "downgrade", "loss", "contract", "recession", "volatile", "risk", "concern",
    "uncertainty", "warning", "caution", "sell", "underweight", "default",
    "inflation", "slowdown", "downturn", "correction", "crash", "crisis",
}
_UNCERTAINTY = {
    "uncertain", "unclear", "mixed", "volatile", "unstable", "unpredictable",
    "risk", "concern", "warning", "caution", "hesitant", "ambiguous",
    "question", "doubt", "worry", "fear", "anxiety",
}


class SentimentAnalyzer:

    def compute_sentiment_score(self, texts: List[str]) -> float:
        """감성 점수 -1.0 ~ +1.0."""
        if not texts:
            return 0.0
        total_pos = total_neg = total_words = 0
        for text in texts:
            words = set(re.findall(r'\b\w+\b', text.lower()))
            total_pos += len(words & _POSITIVE)
            total_neg += len(words & _NEGATIVE)
            total_words += max(len(words), 1)
        if total_pos == 0 and total_neg == 0:
            return 0.0
        score = (total_pos - total_neg) / (total_pos + total_neg + 1e-8)
        density = (total_pos + total_neg) / max(total_words, 1)
        return round(float(max(-1.0, min(1.0, score * min(density * 10, 1.0)))), 4)

    def compute_market_uncertainty(self, texts: List[str]) -> float:
        """시장 불확실성 0.0 ~ 1.0."""
        if not texts:
            return 0.3
        total_u = total_words = 0
        for text in texts:
            words = set(re.findall(r'\b\w+\b', text.lower()))
            total_u += len(words & _UNCERTAINTY)
            total_words += max(len(words), 1)
        density = total_u / max(total_words, 1)
        return round(float(min(density * 20, 1.0)), 4)

    def analyze_batch(self, texts: List[str]) -> Dict[str, float]:
        """sentiment_score + uncertainty + text_count 한 번에 반환."""
        return {
            "sentiment_score": self.compute_sentiment_score(texts),
            "uncertainty": self.compute_market_uncertainty(texts),
            "text_count": len(texts),
        }

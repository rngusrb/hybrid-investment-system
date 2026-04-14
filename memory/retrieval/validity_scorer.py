"""
Retrieval Validity Scoring.

RetrievalScore(case) = Sim(query, case)
                     × RecencyDecay(case_age)
                     × RegimeMatch(current_regime, case_regime)
                     × DataQualityScore(case)
                     × OutcomeReliability(case)

floor 이하 case는 폐기.
"""
import math
from typing import Optional

# 기본값
DEFAULT_FLOOR = 0.4
DEFAULT_RECENCY_HALFLIFE_DAYS = 90  # 90일 반감기


def compute_sim(query: dict, case: dict) -> float:
    """
    가중치 기반 필드 유사도.
    regime/bias 같으면 강한 유사 신호, 나머지는 token overlap.
    """
    case_value = case.get("value", case)

    # regime 정확 매치 보너스
    q_regime = query.get("market_regime", "")
    c_regime = case_value.get("market_regime", "")
    regime_bonus = 0.3 if q_regime and q_regime == c_regime else 0.0

    # bias 정확 매치 보너스
    q_bias = query.get("recommended_market_bias", "")
    c_bias = case_value.get("recommended_market_bias", "")
    bias_bonus = 0.2 if q_bias and q_bias == c_bias else 0.0

    # 기존 token overlap (나머지 필드)
    def tokenize(d: dict) -> set:
        tokens = set()
        for v in d.values():
            if isinstance(v, str):
                tokens.update(v.lower().split())
            elif isinstance(v, (int, float)):
                tokens.add(str(round(v, 1)))
        return tokens

    q_tokens = tokenize(query)
    c_tokens = tokenize(case_value)
    if q_tokens or c_tokens:
        overlap = len(q_tokens & c_tokens) / (len(q_tokens | c_tokens) + 1e-8)
    else:
        overlap = 0.0

    # 최종 점수: token overlap 기반 + regime/bias 보너스, 1.0 clamp
    return min(overlap * 0.5 + regime_bonus + bias_bonus, 1.0)


def compute_recency_decay(case_date: str, as_of: str, halflife_days: int = DEFAULT_RECENCY_HALFLIFE_DAYS) -> float:
    """
    RecencyDecay = exp(-ln(2) * age_days / halflife_days)
    오래된 case일수록 decay.
    """
    try:
        from datetime import datetime
        case_dt = datetime.strptime(case_date, "%Y-%m-%d")
        as_of_dt = datetime.strptime(as_of, "%Y-%m-%d")
        age_days = max(0, (as_of_dt - case_dt).days)
        return math.exp(-math.log(2) * age_days / halflife_days)
    except (ValueError, ZeroDivisionError):
        return 0.0


def compute_regime_match(current_regime: str, case_regime: Optional[str]) -> float:
    """
    RegimeMatch: 동일하면 1.0, 유사하면 0.6, 다르면 0.2.
    """
    if not case_regime:
        return 0.5  # unknown → neutral
    if current_regime == case_regime:
        return 1.0
    # 유사 regime 정의
    similar_pairs = {
        frozenset(["risk_on", "fragile_rebound"]): 0.6,
        frozenset(["risk_on", "mixed"]): 0.5,
        frozenset(["risk_off", "transition"]): 0.6,
        frozenset(["risk_off", "mixed"]): 0.5,
        frozenset(["mixed", "transition"]): 0.7,
        frozenset(["mixed", "fragile_rebound"]): 0.55,
        frozenset(["transition", "fragile_rebound"]): 0.65,
        frozenset(["selective_long", "risk_on"]): 0.7,
        frozenset(["selective_long", "mixed"]): 0.6,
        frozenset(["risk_on", "selective_long"]): 0.7,
    }
    for pair, score in similar_pairs.items():
        if current_regime in pair and case_regime in pair:
            return score
    return 0.2


def compute_data_quality(case: dict) -> float:
    """
    DataQualityScore: case 기록의 completeness 반영.
    필수 필드 존재 여부로 계산.
    """
    required_fields = ["date", "value"]
    optional_fields = ["regime", "tags"]

    present_required = sum(1 for f in required_fields if f in case)
    present_optional = sum(1 for f in optional_fields if f in case)

    if present_required < len(required_fields):
        return 0.1  # 필수 필드 누락 → 낮은 품질

    base = 0.5
    bonus = (present_optional / len(optional_fields)) * 0.5
    return base + bonus


def compute_outcome_reliability(case: dict, review_horizon_days: int = 20) -> float:
    """
    OutcomeReliability: outcome 검증 여부 + 실제 수익률(r_real) 기반 성과 반영.

    Pipeline A (logging_node) r_real_source:
      "polygon_t1"  → 실제 Polygon T+1 데이터 (신뢰)
      "r_sim_proxy" → r_sim 대체값 (낮은 신뢰)

    성과 기반 임계값 (outcome_filler.py의 _update_strategy_memory와 동일):
      r_real >= 0.02 → 1.0  (수익률 2% 이상)
      r_real >= 0    → 0.85 (소폭 양성)
      r_real < 0     → 0.65 (손실)
    """
    case_value = case.get("value", case)
    # outcome 필드 또는 r_real 필드로 검증 여부 확인
    r_real_cv = case_value.get("r_real")
    outcome = case.get("outcome") or r_real_cv

    if outcome is None:
        return 0.3  # outcome 없으면 낮은 신뢰

    # r_real_source == "r_sim_proxy" → 실제 수익률이 아님, 신뢰 낮춤
    # "polygon_t1", "polygon_weighted" 등은 실제 데이터로 신뢰 가능
    r_real_source = case_value.get("r_real_source", "")
    if r_real_source == "r_sim_proxy":
        return 0.5  # proxy값으로 채워진 case — 중간 신뢰

    # horizon_closed + r_real 있으면 성과 기반 신뢰도
    horizon_closed = case.get("horizon_closed", False) or case_value.get("horizon_closed", False)
    if horizon_closed:
        r_real = r_real_cv if r_real_cv is not None else case.get("r_real")
        if r_real is not None:
            if r_real >= 0.02:
                return 1.0
            elif r_real >= 0:
                return 0.85
            else:
                return 0.65
        # horizon_closed이지만 r_real 없음 — 구 포맷 호환, 기존 동작 유지
        return 1.0

    # outcome이 있지만 horizon 미확인
    return 0.6


def compute_validity_score(
    query: dict,
    case: dict,
    as_of: str,
    current_regime: str,
    floor: float = DEFAULT_FLOOR,
) -> Optional[float]:
    """
    RetrievalScore = Sim × RecencyDecay × RegimeMatch × DataQuality × OutcomeReliability

    floor 이하이면 None 반환 (폐기).
    """
    sim = compute_sim(query, case)

    case_date = case.get("date", "")
    recency = compute_recency_decay(case_date, as_of)

    case_regime = case.get("regime") or case.get("value", {}).get("market_regime")
    regime_match = compute_regime_match(current_regime, case_regime)

    data_quality = compute_data_quality(case)
    outcome_rel = compute_outcome_reliability(case)

    score = sim * recency * regime_match * data_quality * outcome_rel

    if score < floor:
        return None  # 폐기
    return round(score, 4)

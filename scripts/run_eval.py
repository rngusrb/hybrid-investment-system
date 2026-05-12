"""
scripts/run_eval.py — E-006 평가 파이프라인 실행기

results/ 아래 portfolio.json 결과를 읽어 시스템 성과와 베이스라인을
CR / ARR / SR / MDD 기준으로 비교하고 eval_YYYY-MM-DD.json으로 저장.

사용법:
    python scripts/run_eval.py
    python scripts/run_eval.py --start 2024-01-01 --end 2024-03-31
    python scripts/run_eval.py --ticker NVDA --output results/eval_custom.json
"""
import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
RESULTS_DIR = ROOT / "results"


# ── 결과 로드 ──────────────────────────────────────────────────────────────

def load_portfolio_results(
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    """results/ 아래 portfolio.json 로드, r_real이 있는 것만 포함."""
    entries = []
    for p in sorted(RESULTS_DIR.glob("*/portfolio.json")):
        run_date = p.parent.name
        if start and run_date < start:
            continue
        if end and run_date > end:
            continue
        try:
            data = json.loads(p.read_text())
            if data.get("r_real") is not None:
                entries.append(data)
        except Exception as e:
            logger.warning(f"portfolio.json 로드 실패 ({run_date}): {e}")
    return entries


# ── 데이터 추출 ────────────────────────────────────────────────────────────

def extract_aapl_price(portfolio_data: dict) -> float | None:
    """stock_results에서 AAPL current_price 추출."""
    for sr in portfolio_data.get("stock_results", []):
        if sr.get("ticker") == "AAPL":
            price = sr.get("current_price")
            if price and float(price) > 0:
                return float(price)
    return None


def extract_aapl_bars(portfolio_data: dict) -> list[dict]:
    """stock_results에서 AAPL bars 추출."""
    for sr in portfolio_data.get("stock_results", []):
        if sr.get("ticker") == "AAPL":
            return sr.get("bars", [])
    return []


# ── 지표 계산 ──────────────────────────────────────────────────────────────

def compute_metrics_for(returns: list[float], label: str, periods_per_year: int = 52) -> dict:
    """
    CR / ARR / SR / MDD + 추가 지표 계산.
    periods_per_year=52: 주간 데이터 기준.
    """
    from evaluation.metrics import (
        compute_total_return,
        compute_annualized_return,
        compute_sharpe,
        compute_max_drawdown,
        compute_sortino,
        compute_win_rate,
    )
    if not returns:
        return {"label": label, "n_periods": 0}

    return {
        "label":              label,
        "n_periods":          len(returns),
        "cumulative_return":  round(compute_total_return(returns), 4),
        "annualized_return":  round(compute_annualized_return(returns, periods_per_year), 4),
        "sharpe_ratio":       round(compute_sharpe(returns, periods_per_year=periods_per_year), 4),
        "sortino_ratio":      round(compute_sortino(returns, periods_per_year=periods_per_year), 4),
        "max_drawdown":       round(compute_max_drawdown(returns), 4),
        "win_rate":           round(compute_win_rate(returns), 4),
    }


# ── 메인 실행 ──────────────────────────────────────────────────────────────

def run_evaluation(
    start: str | None = None,
    end: str | None = None,
    output: str | None = None,
) -> dict:
    """
    평가 파이프라인 실행.
    Returns eval_result dict (저장 + 출력 포함).
    """
    from evaluation.baselines import compute_baseline_returns

    entries = load_portfolio_results(start, end)
    if not entries:
        logger.warning("r_real이 있는 portfolio.json이 없음 — 종료")
        return {}

    logger.info(f"로드된 주기: {len(entries)}개 ({entries[0]['date']} ~ {entries[-1]['date']})")

    # 시스템 수익률
    system_dates  = [e["date"] for e in entries]
    system_returns = [float(e["r_real"]) for e in entries]

    # AAPL 현재가 + bars (베이스라인용)
    aapl_prices       = [extract_aapl_price(e) for e in entries]
    aapl_bars_by_date = {e["date"]: extract_aapl_bars(e) for e in entries}

    # AAPL 가격 없는 날짜 경고
    missing = [system_dates[i] for i, p in enumerate(aapl_prices) if p is None]
    if missing:
        logger.warning(f"AAPL 가격 없는 날짜 {len(missing)}개: {missing}")

    # 베이스라인 수익률 (system_returns[:-1]와 동일 길이)
    # system: 날짜 t의 r_real (기간 [t, t+7] 수익)
    # baseline: 날짜 t → t+1 가격 변화 (같은 기간 proxy)
    baseline_returns = compute_baseline_returns(
        system_dates=system_dates,
        aapl_prices=aapl_prices,
        aapl_bars_by_date=aapl_bars_by_date,
    )

    # 지표 계산
    # 시스템: system_returns 전체 (각 주기의 실제 r_real)
    # 베이스라인: periods - 1개 (연속 가격비)
    metrics = {
        "system":        compute_metrics_for(system_returns,                     "Hybrid System"),
        "buy_and_hold":  compute_metrics_for(baseline_returns["buy_and_hold"],   "Buy & Hold (AAPL)"),
        "macd":          compute_metrics_for(baseline_returns["macd"],            "MACD (12/26/9)"),
        "sma":           compute_metrics_for(baseline_returns["sma"],             "SMA (20)"),
    }

    eval_result = {
        "generated_date":  date.today().isoformat(),
        "period":          f"{system_dates[0]} ~ {system_dates[-1]}",
        "n_periods":       len(system_returns),
        "metrics":         metrics,
        "system_returns":  system_returns,
        "baseline_returns": {k: [round(v, 6) for v in vs] for k, vs in baseline_returns.items()},
    }

    # 저장
    out_path = Path(output) if output else RESULTS_DIR / f"eval_{system_dates[-1]}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(eval_result, indent=2, ensure_ascii=False))
    logger.info(f"저장: {out_path.relative_to(ROOT)}")

    # 출력 테이블
    _print_table(metrics)

    return eval_result


def _print_table(metrics: dict):
    cols = ["cumulative_return", "annualized_return", "sharpe_ratio", "max_drawdown"]
    headers = ["Strategy", "CR", "ARR", "SR", "MDD"]
    rows = []
    for key in ("system", "buy_and_hold", "macd", "sma"):
        m = metrics.get(key, {})
        rows.append([
            m.get("label", key),
            f"{m.get('cumulative_return', 0)*100:.1f}%",
            f"{m.get('annualized_return', 0)*100:.1f}%",
            f"{m.get('sharpe_ratio', 0):.2f}",
            f"{m.get('max_drawdown', 0)*100:.1f}%",
        ])

    col_widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    sep = "  ".join("-" * w for w in col_widths)
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))

    print(f"\n{'='*60}")
    print("  평가 결과 — 시스템 vs 베이스라인")
    print(f"{'='*60}")
    print(f"  {header_line}")
    print(f"  {sep}")
    for row in rows:
        print("  " + "  ".join(v.ljust(col_widths[i]) for i, v in enumerate(row)))
    print(f"{'='*60}\n")


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="평가 파이프라인 실행기")
    parser.add_argument("--start",  help="시작일 YYYY-MM-DD")
    parser.add_argument("--end",    help="종료일 YYYY-MM-DD")
    parser.add_argument("--output", help="출력 JSON 경로 (기본: results/eval_<last_date>.json)")
    args = parser.parse_args()
    run_evaluation(start=args.start, end=args.end, output=args.output)


if __name__ == "__main__":
    main()

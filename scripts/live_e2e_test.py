"""
scripts/live_e2e_test.py

실제 LLM(Anthropic) + Polygon API로 전체 파이프라인 smoke test.
Emily → Bob → Dave → Otto → Policy → Logging 순서로 실행.

실행:
    cd /Users/guhyeongyu/Desktop/hybrid-investment-system
    python scripts/live_e2e_test.py
"""
import os, sys, json, time
from pathlib import Path

# .env 로드
_root = Path(__file__).parent.parent.resolve()
_env = _root / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(_root))

from data.polygon_fetcher import PolygonFetcher
from data.data_manager import DataManager
from simulation.trading_engine import SimulatedTradingEngine
from llm.factory import create_provider
from agents.emily import EmilyAgent
from agents.bob import BobAgent
from agents.dave import DaveAgent
from agents.otto import OttoAgent
from graph.nodes.policy import daily_policy_selection
from graph.nodes.logging_node import daily_post_execution_logging
from graph.state import make_initial_state

# ─── 설정 ────────────────────────────────────────────────────
DATE        = "2024-01-19"   # 테스트 기준일 (금요일)
TICKER      = "SPY"
POLY_KEY    = os.environ.get("POLYGON_API_KEY", "rDrRIWoHnZPSjaNoYmeUfJRWMuDd_Ntk")
# ─────────────────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []   # (step, status, detail)


def record(step: str, ok: bool, detail: str = ""):
    tag = PASS if ok else FAIL
    results.append((step, tag, detail))
    print(f"  {tag}  {step}" + (f"  — {detail}" if detail else ""))


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ════════════════════════════════════════════════════════════
# STEP 1: Polygon OHLCV
# ════════════════════════════════════════════════════════════
section("STEP 1 · Polygon API — SPY OHLCV")
t0 = time.time()
fetcher = PolygonFetcher(api_key=POLY_KEY)
ohlcv = fetcher.get_ohlcv(TICKER, "2023-07-03", DATE, as_of=DATE)
bars = ohlcv["data"]
elapsed = time.time() - t0

record("Polygon client init", fetcher._client is not None)
record("OHLCV bars received", len(bars) >= 30, f"{len(bars)} bars in {elapsed:.1f}s")
record("First bar has OHLCV", all(k in bars[0] for k in ("open","high","low","close","volume")) if bars else False,
       f"close={bars[0]['close']} date={bars[0]['date']}" if bars else "no bars")
record("Last bar date ≤ as_of", bars[-1]["date"] <= DATE if bars else False,
       f"last bar={bars[-1]['date']}" if bars else "")

# ════════════════════════════════════════════════════════════
# STEP 2: SimulatedTradingEngine (Polygon real data)
# ════════════════════════════════════════════════════════════
section("STEP 2 · SimulatedTradingEngine — real backtest")
engine = SimulatedTradingEngine(fetcher=fetcher)
t0 = time.time()
metrics = engine.run_strategy(
    strategy_type="momentum",
    sim_window={"train_start": "2023-01-03", "train_end": "2024-01-18"},
    regime_fit=0.7,
    technical_alignment=0.6,
    ticker=TICKER,
)
elapsed = time.time() - t0

record("run_strategy returns dict", isinstance(metrics, dict), str(metrics) if metrics else "None")
record("data_source = real", metrics.get("data_source") == "real" if metrics else False,
       metrics.get("data_source","?") if metrics else "")
record("sharpe finite", metrics is not None and abs(metrics.get("sharpe",0)) < 50,
       f"sharpe={metrics.get('sharpe'):.4f}" if metrics else "")
record("mdd in [0,1]", metrics is not None and 0 <= metrics.get("mdd",99) <= 1,
       f"mdd={metrics.get('mdd'):.4f}" if metrics else "")
record("hit_rate in [0,1]", metrics is not None and 0 <= metrics.get("hit_rate",99) <= 1,
       f"hit_rate={metrics.get('hit_rate'):.4f}" if metrics else "")
if metrics:
    print(f"\n  📊 Backtest metrics ({elapsed:.1f}s):")
    for k, v in metrics.items():
        if k != "data_source":
            print(f"     {k:12s} = {v:.4f}")
    print(f"     {'data_source':12s} = {metrics['data_source']}")

# ════════════════════════════════════════════════════════════
# STEP 3: Polygon news
# ════════════════════════════════════════════════════════════
section("STEP 3 · Polygon API — SPY News")
t0 = time.time()
news = fetcher.get_news(TICKER, "2024-01-12", DATE, as_of=DATE, limit=5)
articles = news.get("articles", [])
elapsed = time.time() - t0
record("News endpoint responds", True, f"{len(articles)} articles in {elapsed:.1f}s")
if articles:
    record("Article has title", "title" in articles[0], articles[0].get("title","?")[:80])

# ════════════════════════════════════════════════════════════
# STEP 4: Emily (LLM)
# ════════════════════════════════════════════════════════════
section("STEP 4 · Emily Agent — LLM market analysis")

# 시장 데이터 요약 생성
dm = DataManager()
import pandas as pd
df = dm.preprocess_ohlcv(bars[-30:])   # 최근 30일
df = dm.compute_returns(df)
recent_returns = df["return"].dropna().tolist()
last_close = bars[-1]["close"]
prev_close = bars[-2]["close"] if len(bars) >= 2 else last_close
daily_ret = (last_close - prev_close) / prev_close

market_input = {
    "date": DATE,
    "ticker": TICKER,
    "price": last_close,
    "daily_return": round(daily_ret, 4),
    "20d_avg_return": round(sum(recent_returns[-20:]) / 20, 5) if len(recent_returns) >= 20 else 0,
    "20d_vol": round(pd.Series(recent_returns[-20:]).std(), 5) if len(recent_returns) >= 20 else 0.01,
    "news_headlines": [a.get("title","") for a in articles[:3]],
    "no_news": news.get("no_news_label") or (len(articles) == 0),
}

llm = create_provider(node_role="analyst")   # haiku (빠름)
emily_config = {
    "name": "Emily",
    "system_prompt_path": "prompts/emily_system.md",
    "temperature": 0.2,
    "max_tokens": 2048,
    "max_retries": 3,
    "agent_confidence_floor": 0.45,
}
emily_agent = EmilyAgent(llm=llm, config=emily_config)

t0 = time.time()
try:
    emily_output = emily_agent.run(market_input, state={})
    elapsed = time.time() - t0
    record("Emily LLM call succeeded", True, f"{elapsed:.1f}s")
    record("Emily market_regime", "market_regime" in emily_output,
           emily_output.get("market_regime","?"))
    record("Emily regime_confidence", 0 < emily_output.get("regime_confidence",0) <= 1,
           f"{emily_output.get('regime_confidence'):.2f}")
    record("Emily technical_signal_state present", "technical_signal_state" in emily_output)
    record("Emily recommended_market_bias", "recommended_market_bias" in emily_output,
           emily_output.get("recommended_market_bias","?"))
    print(f"\n  🧠 Emily output:")
    print(f"     regime          = {emily_output.get('market_regime')}")
    print(f"     confidence      = {emily_output.get('regime_confidence'):.2f}")
    print(f"     bias            = {emily_output.get('recommended_market_bias')}")
    ts = emily_output.get("technical_signal_state", {})
    print(f"     tech_direction  = {ts.get('trend_direction')}")
    print(f"     tech_confidence = {ts.get('technical_confidence'):.2f}")
    print(f"     reversal_risk   = {ts.get('reversal_risk'):.2f}")
except Exception as e:
    elapsed = time.time() - t0
    record("Emily LLM call succeeded", False, str(e)[:120])
    emily_output = None

# ════════════════════════════════════════════════════════════
# STEP 5: Emily → Bob packet + Bob (LLM)
# ════════════════════════════════════════════════════════════
section("STEP 5 · Bob Agent — strategy selection + real backtest")

emily_to_bob = None
bob_output = None

if emily_output:
    emily_to_bob = emily_agent.to_bob_packet(emily_output, DATE)
    record("Emily→Bob packet built", bool(emily_to_bob),
           f"regime={emily_to_bob.get('regime')} confidence={emily_to_bob.get('regime_confidence'):.2f}")

    bob_config = {
        "name": "Bob",
        "system_prompt_path": "prompts/bob_system.md",
        "temperature": 0.2,
        "max_tokens": 3000,
        "max_retries": 3,
        "agent_confidence_floor": 0.45,
    }
    bob_agent = BobAgent(llm=llm, config=bob_config, trading_engine=engine)
    t0 = time.time()
    try:
        bob_output = bob_agent.run(emily_to_bob, state={})
        elapsed = time.time() - t0
        candidates = bob_output.get("candidate_strategies", [])
        selected = bob_output.get("selected_for_review", [])
        record("Bob LLM call succeeded", True, f"{elapsed:.1f}s")
        record("Bob has candidates", len(candidates) > 0, f"{len(candidates)} candidates")
        record("Bob selected_for_review", len(selected) > 0, str(selected))
        # sim_metrics 확인 (real backtest enrichment)
        has_real = any(c.get("sim_metrics",{}).get("sharpe") is not None for c in candidates)
        record("Bob sim_metrics enriched", has_real)
        print(f"\n  📋 Bob candidates:")
        for c in candidates:
            sm = c.get("sim_metrics", {})
            source = "(real)" if c.get("sim_metrics") else "(LLM)"
            print(f"     [{c['name']}] type={c.get('type')} conf={c.get('confidence'):.2f} "
                  f"sharpe={sm.get('sharpe','?')} {source}")
    except Exception as e:
        elapsed = time.time() - t0
        record("Bob LLM call succeeded", False, str(e)[:120])
else:
    record("Bob skipped (Emily failed)", False, "upstream failure")

# ════════════════════════════════════════════════════════════
# STEP 6: Bob → Dave packet + Dave (LLM)
# ════════════════════════════════════════════════════════════
section("STEP 6 · Dave Agent — risk assessment")

dave_output = None
bob_to_dave = None

if bob_output and emily_output:
    bob_agent_inst = BobAgent(llm=llm, config={"name":"Bob","max_retries":1,"agent_confidence_floor":0.45},
                              trading_engine=engine)
    bob_to_dave = bob_agent_inst.to_dave_packet(bob_output, DATE)
    record("Bob→Dave packet built", bool(bob_to_dave),
           f"strategy={bob_to_dave.get('strategy_name')}")

    dave_config = {
        "name": "Dave",
        "system_prompt_path": "prompts/dave_system.md",
        "temperature": 0.2,
        "max_tokens": 2048,
        "max_retries": 3,
        "agent_confidence_floor": 0.45,
    }
    dave_agent = DaveAgent(llm=llm, config=dave_config)
    t0 = time.time()
    try:
        dave_output = dave_agent.run(bob_to_dave, state={})
        elapsed = time.time() - t0
        record("Dave LLM call succeeded", True, f"{elapsed:.1f}s")
        record("Dave risk_score in [0,1]", 0 <= dave_output.get("risk_score",99) <= 1,
               f"{dave_output.get('risk_score'):.3f}")
        record("Dave risk_constraints present", bool(dave_output.get("risk_constraints")))
        record("Dave stress_test present", bool(dave_output.get("stress_test")))
        print(f"\n  🛡️  Dave output:")
        print(f"     risk_score     = {dave_output.get('risk_score'):.3f}")
        print(f"     risk_level     = {dave_output.get('risk_level')}")
        print(f"     trigger_alert  = {dave_output.get('trigger_risk_alert_meeting')}")
        rc = dave_output.get("risk_constraints", {})
        print(f"     max_beta       = {rc.get('max_beta')}")
        print(f"     max_exposure   = {rc.get('max_gross_exposure')}")
    except Exception as e:
        elapsed = time.time() - t0
        record("Dave LLM call succeeded", False, str(e)[:120])
else:
    record("Dave skipped (upstream failed)", False)

# ════════════════════════════════════════════════════════════
# STEP 7: Otto (LLM)
# ════════════════════════════════════════════════════════════
section("STEP 7 · Otto Agent — fund manager policy")

otto_output_llm = None

if dave_output and bob_output and emily_output:
    from transforms.all_to_otto import transform_all_to_otto

    bob_to_exec = bob_agent_inst.to_execution_packet(bob_output, DATE)

    try:
        otto_packet = transform_all_to_otto(
            emily_packet=emily_to_bob,
            bob_dave_packet=bob_to_dave,
            dave_output=dave_output,
            execution_packet=bob_to_exec,
            date=DATE,
        )
        record("all_to_otto transform", True, f"keys={list(otto_packet.keys())[:5]}...")

        otto_config = {
            "name": "Otto",
            "system_prompt_path": "prompts/otto_system.md",
            "temperature": 0.1,
            "max_tokens": 2048,
            "max_retries": 3,
            "agent_confidence_floor": 0.45,
            "dual_reward": {"lambda1":0.3,"lambda2":0.2,"lambda3":0.15,"lambda4":0.2,"lambda5":0.15},
        }
        otto_agent = OttoAgent(llm=llm, config=otto_config)
        t0 = time.time()
        otto_output_llm = otto_agent.run(otto_packet, state={})
        elapsed = time.time() - t0
        record("Otto LLM call succeeded", True, f"{elapsed:.1f}s")
        record("Otto approval_status valid",
               otto_output_llm.get("approval_status") in
               ("approved","approved_with_modification","conditional_approval","rejected"),
               otto_output_llm.get("approval_status","?"))
        record("Otto selected_policy present", bool(otto_output_llm.get("selected_policy")),
               otto_output_llm.get("selected_policy","?"))
        print(f"\n  🎯 Otto output:")
        print(f"     approval_status  = {otto_output_llm.get('approval_status')}")
        print(f"     selected_policy  = {otto_output_llm.get('selected_policy')}")
        alloc = otto_output_llm.get("allocation", {})
        print(f"     allocation       = {alloc}")
        print(f"     reasoning        = {(otto_output_llm.get('policy_reasoning_summary') or ['?'])[0][:80]}")
    except Exception as e:
        record("Otto LLM call succeeded", False, str(e)[:120])
else:
    record("Otto skipped (upstream failed)", False)

# ════════════════════════════════════════════════════════════
# STEP 8: Policy node (utility) + Logging node
# ════════════════════════════════════════════════════════════
section("STEP 8 · Policy node + Logging node")

state = make_initial_state(DATE, cycle_type="daily")
state["emily_output"] = emily_output
state["bob_output"] = bob_output
state["dave_output"] = dave_output
state["otto_output"] = otto_output_llm
state["risk_score"] = dave_output.get("risk_score", 0.5) if dave_output else 0.5
state["execution_feasibility_score"] = 0.72
state["agent_reliability"] = {"emily": 0.65, "bob": 0.62, "dave": 0.68, "otto": 0.70}

try:
    state = daily_policy_selection(state)
    otto_final = state.get("otto_output", {})
    record("policy_selection runs", True)
    record("utility_score in output", "utility_score" in otto_final,
           f"utility={otto_final.get('utility_score')}")
    record("approval_status set", bool(otto_final.get("approval_status")),
           otto_final.get("approval_status","?"))
    print(f"\n  ⚙️  Policy node:")
    print(f"     approval_status = {otto_final.get('approval_status')}")
    print(f"     utility_score   = {otto_final.get('utility_score')}")
    print(f"     policy_action   = {otto_final.get('policy_action')}")
except Exception as e:
    record("policy_selection runs", False, str(e)[:120])

try:
    state = daily_post_execution_logging(state)
    record("logging_node runs", True)
    from memory.registry import strategy_memory
    outcome = strategy_memory._store.get(f"outcome_{DATE}")
    record("outcome stored in strategy_memory", outcome is not None)
    if outcome:
        val = outcome.get("value", {})
        record("r_real == r_sim", val.get("r_real") == val.get("r_sim"),
               f"r_sim={val.get('r_sim'):.4f} r_real={val.get('r_real'):.4f}")
except Exception as e:
    record("logging_node runs", False, str(e)[:120])

# ════════════════════════════════════════════════════════════
# FINAL SUMMARY TABLE
# ════════════════════════════════════════════════════════════
section("FINAL RESULTS")

passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
total  = len(results)

col_w = [max(len(r[0]) for r in results) + 2, 8, 60]
header = f"{'Check':<{col_w[0]}} {'Result':<{col_w[1]}} {'Detail'}"
print(f"\n  {header}")
print(f"  {'-'*sum(col_w)}")
for step, status, detail in results:
    detail_trunc = detail[:55] + "..." if len(detail) > 58 else detail
    print(f"  {step:<{col_w[0]}} {status:<{col_w[1]}} {detail_trunc}")

print(f"\n  {'─'*sum(col_w)}")
print(f"  총 {total}개 체크   {PASS} {passed}개   {FAIL} {failed}개")

# ── 결과 파일 저장 ────────────────────────────────────────
import datetime
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

md_lines = [
    "# Live E2E Test Results",
    f"",
    f"**실행일시**: {now}  ",
    f"**테스트 기준일**: {DATE}  ",
    f"**LLM**: Anthropic claude-haiku-4-5 (analyst role)  ",
    f"**데이터**: Polygon SPY  ",
    f"",
    f"## 결과 요약",
    f"",
    f"| 체크 항목 | 결과 | 상세 |",
    f"|-----------|------|------|",
]
for step, status, detail in results:
    detail_escaped = detail.replace("|", "\\|")[:80]
    md_lines.append(f"| {step} | {status} | {detail_escaped} |")

md_lines += [
    f"",
    f"**총 {total}개 체크 — PASS {passed} / FAIL {failed}**",
    f"",
    f"## 단계별 설명",
    f"",
    f"| 단계 | 내용 |",
    f"|------|------|",
    f"| STEP 1 | Polygon API — SPY OHLCV 실제 데이터 수신 |",
    f"| STEP 2 | SimulatedTradingEngine — 실제 시세로 momentum 백테스트 |",
    f"| STEP 3 | Polygon API — SPY 뉴스 수신 |",
    f"| STEP 4 | Emily Agent — LLM 시장 분석 (regime, technical signal) |",
    f"| STEP 5 | Bob Agent — LLM 전략 선택 + 실제 백테스트 sim_metrics 교체 |",
    f"| STEP 6 | Dave Agent — LLM 리스크 평가 |",
    f"| STEP 7 | Otto Agent — LLM 최종 정책 결정 |",
    f"| STEP 8 | policy_selection 노드 (utility_score) + logging_node (r_real=r_sim) |",
]

out_path = _root / "LIVE_E2E_RESULTS.md"
out_path.write_text("\n".join(md_lines))
print(f"\n  📄 결과 저장 → {out_path}")

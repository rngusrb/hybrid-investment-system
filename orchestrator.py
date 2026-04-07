"""
Orchestrator — 메인 진입점.
daily/weekly/event-driven cycle 관리.
"""
import logging
import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from graph.builder import compile_graph
from graph.state import make_initial_state, SystemState
from ledger.shared_ledger import SharedLedger
from meetings.market_analysis import MarketAnalysisMeeting
from meetings.strategy_development import StrategyDevelopmentMeeting
from meetings.risk_alert import RiskAlertMeeting

load_dotenv()
logger = logging.getLogger(__name__)


class Orchestrator:
    """
    전체 시스템 진입점.
    LLM + Polygon fetcher를 state에 주입 → 노드가 실제 에이전트 호출.
    raw data는 ingest 노드에서만 다룸 — Otto에게 직접 전달 경로 없음.
    """

    def __init__(self, config: dict = None, use_real_llm: bool = False):
        self.config = config or {}
        self.ledger = SharedLedger()
        self.app = compile_graph()

        self.market_meeting = MarketAnalysisMeeting(ledger=self.ledger, config=config)
        self.strategy_meeting = StrategyDevelopmentMeeting(ledger=self.ledger, config=config)
        self.risk_alert_meeting = RiskAlertMeeting(ledger=self.ledger, config=config)

        # LLM + fetcher 초기화 (실패해도 placeholder fallback)
        self._llm_analyst = None
        self._llm_decision = None
        self._polygon_fetcher = None

        if use_real_llm:
            self._init_providers()

    def _init_providers(self):
        """LLM provider + Polygon fetcher 초기화."""
        try:
            from llm.factory import create_provider
            self._llm_analyst = create_provider(node_role="analyst")
            self._llm_decision = create_provider(node_role="decision")
            logger.info("[Orchestrator] LLM providers initialized")
        except Exception as e:
            logger.warning(f"[Orchestrator] LLM init failed — placeholder mode: {e}")

        try:
            from data.polygon_fetcher import PolygonFetcher
            api_key = os.getenv("POLYGON_API_KEY")
            if api_key:
                self._polygon_fetcher = PolygonFetcher(api_key=api_key)
                logger.info("[Orchestrator] Polygon fetcher initialized")
        except Exception as e:
            logger.warning(f"[Orchestrator] Polygon init failed: {e}")

    def _inject_providers(self, state: dict) -> dict:
        """LLM + fetcher를 state에 주입."""
        if self._llm_analyst:
            state["_llm_analyst"] = self._llm_analyst
        if self._llm_decision:
            state["_llm_decision"] = self._llm_decision
        if self._polygon_fetcher:
            state["_polygon_fetcher"] = self._polygon_fetcher
        return state

    def run_daily_cycle(self, current_date: str, market_data: Optional[dict] = None) -> dict:
        """
        일간 cycle 실행.
        raw data는 state에 넣고 INGEST_DAILY_DATA 노드에서 처리.
        Otto에게 raw data 직접 전달하는 경로 없음.
        """
        logger.info(f"[Orchestrator] Daily cycle: {current_date}")

        state = make_initial_state(current_date, cycle_type="daily")
        state = self._inject_providers(state)

        if market_data:
            state["raw_market_data"] = market_data

        result = self.app.invoke(state)

        approval = (result.get("otto_output") or {}).get("approval_status", "-")
        logger.info(
            f"[Orchestrator] Daily cycle complete: "
            f"risk_score={result.get('risk_score', 0):.2f} approval={approval}"
        )
        return result

    def run_weekly_cycle(self, current_date: str, market_data: Optional[dict] = None) -> dict:
        """
        주간 cycle 실행 (Market Analysis + Strategy Development + Propagation Audit).
        """
        logger.info(f"[Orchestrator] Weekly cycle: {current_date}")

        state = make_initial_state(current_date, cycle_type="weekly", is_week_end=True)
        state = self._inject_providers(state)

        if market_data:
            state["raw_market_data"] = market_data

        state = self.market_meeting.run(state)
        state = self.strategy_meeting.run(state)

        result = self.app.invoke(state)
        logger.info(
            f"[Orchestrator] Weekly cycle complete: "
            f"weekly_report={result.get('weekly_market_report') is not None}"
        )
        return result

    def run_risk_alert_cycle(self, current_date: str, trigger_reason: str = "") -> dict:
        """event-driven risk alert cycle."""
        logger.info(f"[Orchestrator] Risk alert cycle: {current_date}, reason: {trigger_reason}")

        state = make_initial_state(current_date, cycle_type="event")
        state = self._inject_providers(state)
        state["risk_alert_triggered"] = True
        state["flow_decision_reason"] = trigger_reason

        state = self.risk_alert_meeting.run(state)
        result = self.app.invoke(state)
        logger.info("[Orchestrator] Risk alert cycle complete")
        return result

    def get_ledger_summary(self) -> dict:
        """현재까지 ledger에 기록된 공식 output 요약."""
        entries = self.ledger.get_all()
        summary = {}
        for e in entries:
            t = e["entry_type"]
            summary[t] = summary.get(t, 0) + 1
        return {"total_entries": len(entries), "by_type": summary}

    @staticmethod
    def is_week_end(date_str: str) -> bool:
        """금요일 여부 확인 (0=Monday, 4=Friday)."""
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            return d.weekday() == 4
        except ValueError:
            return False


def main():
    """메인 진입점."""
    logging.basicConfig(level=logging.INFO)
    orchestrator = Orchestrator(use_real_llm=True)

    result = orchestrator.run_daily_cycle("2024-01-15")

    oo = result.get("otto_output") or {}
    print(f"\n{'='*50}")
    print(f"날짜:       2024-01-15")
    print(f"승인 여부:  {oo.get('approval_status', result.get('approval_status', '-'))}")
    print(f"전략:       {oo.get('selected_policy', '-')}")
    print(f"리스크:     {result.get('risk_score', '-')}")
    print(f"유틸리티:   {result.get('utility_score', '-')}")
    print(f"배분:       {oo.get('allocation', '-')}")
    print(f"{'='*50}")
    print(f"Ledger: {orchestrator.get_ledger_summary()}")


if __name__ == "__main__":
    main()

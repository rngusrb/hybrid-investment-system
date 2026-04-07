"""Weekly Strategy Development Meeting."""
from meetings.base_meeting import BaseMeeting
from schemas.meeting_schema import WeeklyStrategySet
from transforms.bob_to_execution import transform_bob_to_execution
from ledger.shared_ledger import SharedLedger


class StrategyDevelopmentMeeting(BaseMeeting):
    """
    Weekly Strategy Development Meeting.
    selected strategy는 실행 명령이 아님 — execution feasibility packet 별도 생성.
    """

    def run(self, state: dict) -> dict:
        updated = dict(state)
        date = state.get("current_date", "")
        bob_output = state.get("bob_output") or {}

        # selected strategies
        candidates = bob_output.get("candidate_strategies", [])
        selected = bob_output.get("selected_for_review", [])

        # rejection reasons: confidence < floor인 것들
        rejections = {}
        confidence_floor = 0.45
        for c in candidates:
            if c.get("confidence", 1.0) < confidence_floor:
                rejections[c["name"]] = f"confidence={c['confidence']} below floor={confidence_floor}"

        # execution feasibility hints: 선택된 전략의 turnover/technical_alignment 기반
        exec_hints = []
        for c in candidates:
            if c["name"] in selected:
                turnover = c.get("sim_metrics", {}).get("turnover", 0.0)
                tech_align = c.get("technical_alignment", 1.0)
                if turnover > 0.5:
                    exec_hints.append(f"{c['name']}: high_turnover={turnover:.2f} → consider staggered entry")
                if tech_align < 0.4:
                    exec_hints.append(f"{c['name']}: low_tech_alignment={tech_align:.2f} → add hedge")

        strategy_set = WeeklyStrategySet(
            date=date,
            candidate_strategies=[c["name"] for c in candidates],
            selected_strategies=selected,
            rejection_reasons=rejections,
            optimization_notes=[
                note
                for c in candidates
                for note in c.get("optimization_suggestions", [])
            ],
            execution_feasibility_hints=exec_hints,
            technical_alignment_summary=self._summarize_technical_alignment(candidates),
        )
        updated["weekly_strategy_set"] = strategy_set.model_dump()

        # 핵심: execution feasibility packet 별도 생성
        # selected strategy를 바로 execution order로 취급하지 않음
        if bob_output and candidates:
            exec_packet = transform_bob_to_execution(bob_output, date)
            updated["bob_to_execution_packet"] = exec_packet

        # Ledger 기록
        self._record_to_ledger("candidate_strategy_summary", strategy_set.model_dump(), date, "StrategyDevelopmentMeeting")

        return updated

    def _summarize_technical_alignment(self, candidates: list) -> str:
        if not candidates:
            return "No candidates"
        avg_alignment = sum(c.get("technical_alignment", 0.5) for c in candidates) / len(candidates)
        return f"Average technical alignment: {avg_alignment:.2f} across {len(candidates)} candidates"

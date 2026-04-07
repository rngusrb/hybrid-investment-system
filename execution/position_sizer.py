"""
execution.position_sizer — 포트폴리오 배분 → 실제 주문 수량 변환.

Otto의 allocation(equities/hedge/cash %) + 현재 가격 + 계좌 잔고 기반으로
실제 매수/매도 수량과 notional 금액을 계산.

브로커 연결 없이도 "어떤 종목을 몇 주" 출력.
실제 브로커 연결 시 이 모듈의 OrderPlan을 브로커 API에 전달하면 됨.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OrderLine:
    """단일 종목 주문."""
    ticker: str
    direction: str          # "buy" | "sell" | "hold"
    shares: int             # 정수 단위 (소수 주식 미지원)
    notional: float         # 주문 금액 (shares * price)
    price: float            # 기준 가격 (현재 close)
    stop_loss_price: float  # 손절가 (price * (1 - stop_loss_pct))
    entry_style: str        # "immediate" | "staggered" | "phased" | "hold"
    note: str = ""


@dataclass
class OrderPlan:
    """전략 실행을 위한 전체 주문 계획."""
    date: str
    portfolio_value: float
    strategy_name: str
    approval_status: str
    orders: list[OrderLine] = field(default_factory=list)
    cash_reserved: float = 0.0       # 현금 유보 금액
    hedge_notional: float = 0.0      # 헤지 배분 금액
    estimated_slippage: float = 0.0  # 추정 슬리피지 (0.1% 기준)
    feasibility_score: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "portfolio_value": self.portfolio_value,
            "strategy_name": self.strategy_name,
            "approval_status": self.approval_status,
            "orders": [
                {
                    "ticker": o.ticker,
                    "direction": o.direction,
                    "shares": o.shares,
                    "notional": round(o.notional, 2),
                    "price": o.price,
                    "stop_loss_price": round(o.stop_loss_price, 2),
                    "entry_style": o.entry_style,
                    "note": o.note,
                }
                for o in self.orders
            ],
            "cash_reserved": round(self.cash_reserved, 2),
            "hedge_notional": round(self.hedge_notional, 2),
            "estimated_slippage": round(self.estimated_slippage, 2),
            "feasibility_score": self.feasibility_score,
            "warnings": self.warnings,
        }


# 기본 추정 슬리피지 비율 (대형주 기준 0.05%)
_DEFAULT_SLIPPAGE_BPS = 5  # basis points


class PositionSizer:
    """
    Otto allocation → 실제 주문 계획 변환기.

    Args:
        portfolio_value: 총 계좌 잔고 (USD)
        current_prices: {"SPY": 500.0, "SH": 41.0, ...} 종목별 현재 가격
        slippage_bps: 슬리피지 추정치 (basis points, default 5bps)
    """

    def __init__(
        self,
        portfolio_value: float,
        current_prices: dict[str, float],
        slippage_bps: int = _DEFAULT_SLIPPAGE_BPS,
    ):
        if portfolio_value <= 0:
            raise ValueError(f"portfolio_value must be positive, got {portfolio_value}")
        self.portfolio_value = portfolio_value
        self.current_prices = current_prices
        self.slippage_bps = slippage_bps

    def compute(
        self,
        allocation: dict,
        execution_plan: dict,
        strategy_name: str,
        approval_status: str,
        date: str,
        equity_ticker: str = "SPY",
        hedge_ticker: str = "SH",
        feasibility_score: float = 0.8,
    ) -> OrderPlan:
        """
        Otto allocation을 기반으로 OrderPlan 생성.

        Args:
            allocation: {"equities": 0.6, "hedge": 0.1, "cash": 0.3}
            execution_plan: {"entry_style": "staggered", "stop_loss": 0.05, ...}
            equity_ticker: 주식 매수에 사용할 종목 (default "SPY")
            hedge_ticker: 헤지에 사용할 종목 (default "SH" = inverse SPY)
        """
        warnings = []

        equities_pct = float(allocation.get("equities", 0.0))
        hedge_pct = float(allocation.get("hedge", 0.0))
        cash_pct = float(allocation.get("cash", 0.0))

        # 합계 검증 (합이 1.0 초과하면 비례 정규화)
        total = equities_pct + hedge_pct + cash_pct
        if total > 1.05:
            warnings.append(f"Allocation sum {total:.2f} > 1.0 — normalized")
            equities_pct /= total
            hedge_pct /= total
            cash_pct /= total

        entry_style = execution_plan.get("entry_style", "staggered")
        stop_loss_pct = float(execution_plan.get("stop_loss", 0.05))

        orders = []
        estimated_slippage = 0.0

        # 주식 주문 (equities 배분)
        equity_notional = self.portfolio_value * equities_pct
        equity_price = self.current_prices.get(equity_ticker)
        if equity_price and equity_price > 0 and equity_notional > 0:
            shares = math.floor(equity_notional / equity_price)
            if shares > 0:
                actual_notional = shares * equity_price
                stop_price = equity_price * (1.0 - stop_loss_pct)
                slip = actual_notional * (self.slippage_bps / 10000.0)
                estimated_slippage += slip
                orders.append(OrderLine(
                    ticker=equity_ticker,
                    direction="buy",
                    shares=shares,
                    notional=actual_notional,
                    price=equity_price,
                    stop_loss_price=stop_price,
                    entry_style=entry_style,
                    note=f"{equities_pct*100:.0f}% allocation",
                ))
            else:
                warnings.append(f"equity_notional={equity_notional:.0f} too small for 1 share of {equity_ticker}@{equity_price}")
        elif equity_notional > 0:
            warnings.append(f"No price available for {equity_ticker} — skipping equity order")

        # 헤지 주문 (hedge 배분 → inverse ETF)
        hedge_notional = self.portfolio_value * hedge_pct
        hedge_price = self.current_prices.get(hedge_ticker)
        if hedge_price and hedge_price > 0 and hedge_notional > 0:
            hedge_shares = math.floor(hedge_notional / hedge_price)
            if hedge_shares > 0:
                actual_hedge_notional = hedge_shares * hedge_price
                slip = actual_hedge_notional * (self.slippage_bps / 10000.0)
                estimated_slippage += slip
                orders.append(OrderLine(
                    ticker=hedge_ticker,
                    direction="buy",
                    shares=hedge_shares,
                    notional=actual_hedge_notional,
                    price=hedge_price,
                    stop_loss_price=0.0,  # 헤지는 손절 없음
                    entry_style=entry_style,
                    note=f"{hedge_pct*100:.0f}% hedge allocation",
                ))

        cash_reserved = self.portfolio_value * cash_pct

        return OrderPlan(
            date=date,
            portfolio_value=self.portfolio_value,
            strategy_name=strategy_name,
            approval_status=approval_status,
            orders=orders,
            cash_reserved=cash_reserved,
            hedge_notional=hedge_notional,
            estimated_slippage=estimated_slippage,
            feasibility_score=feasibility_score,
            warnings=warnings,
        )

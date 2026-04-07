"""Simulation package — Simulated Trading Engine for Bob's strategy validation."""
from simulation.trading_engine import SimulatedTradingEngine
from simulation.strategy_executor import StrategyExecutor
from simulation.synthetic_provider import SyntheticDataProvider

__all__ = ["SimulatedTradingEngine", "StrategyExecutor", "SyntheticDataProvider"]

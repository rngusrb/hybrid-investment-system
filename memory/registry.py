"""Memory Registry — 싱글톤 memory 및 retriever 인스턴스 중앙 관리."""
from memory.market_memory import MarketMemory
from memory.strategy_memory import StrategyMemory
from memory.reports_memory import ReportsMemory
from memory.retrieval.retriever import Retriever

# 싱글톤 memory 인스턴스
market_memory = MarketMemory()
strategy_memory = StrategyMemory()
reports_memory = ReportsMemory()

# 각 memory에 대응하는 Retriever 인스턴스
market_retriever = Retriever(market_memory, floor=0.3, top_k=7)
strategy_retriever = Retriever(strategy_memory, floor=0.3, top_k=5)
reports_retriever = Retriever(reports_memory, floor=0.3, top_k=5)

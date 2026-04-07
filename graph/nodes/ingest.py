"""INGEST_DAILY_DATA node — PolygonFetcher로 실제 데이터 수집."""
from graph.state import SystemState


def ingest_daily_data(state: SystemState) -> SystemState:
    """
    시장 데이터 ingest.
    _polygon_fetcher가 state에 있으면 실제 Polygon API 호출.
    없으면 raw_market_data가 이미 있는지 확인 후 진행.
    """
    updated = dict(state)
    date = state.get("current_date", "")

    # 이미 데이터 있으면 스킵
    if state.get("raw_market_data") is not None:
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": "INGEST_DAILY_DATA",
            "reason": "raw_market_data already present",
            "date": date,
        }]
        updated["next_node"] = "UPDATE_MARKET_MEMORY"
        return updated

    fetcher = state.get("_polygon_fetcher")

    if fetcher is not None and date:
        # 실제 Polygon API 호출
        try:
            from datetime import datetime, timedelta
            dt = datetime.strptime(date, "%Y-%m-%d")
            from_date = (dt - timedelta(days=180)).strftime("%Y-%m-%d")

            ohlcv = fetcher.get_ohlcv(
                ticker="SPY",
                from_date=from_date,
                to_date=date,
                as_of=date,
            )
            news_from = (dt - timedelta(days=14)).strftime("%Y-%m-%d")
            news = fetcher.get_news(
                ticker="SPY",
                from_date=news_from,
                to_date=date,
                as_of=date,
                limit=20,
            )
            updated["raw_market_data"] = {
                "ohlcv": ohlcv.get("data", []),
                "ticker": "SPY",
                "quality": ohlcv.get("quality"),
            }
            updated["raw_news"] = news.get("articles", [])
        except Exception as e:
            # API 실패 → 빈 데이터 + 품질 플래그 (예외 발생 금지)
            updated["raw_market_data"] = {"ohlcv": [], "ticker": "SPY", "error": str(e)}
            updated["raw_news"] = []
            updated["skip_log"] = list(state.get("skip_log", [])) + [{
                "node": "INGEST_DAILY_DATA",
                "reason": f"polygon_api_failure: {e}",
                "date": date,
            }]
    else:
        # fetcher 없음 → placeholder
        updated["raw_market_data"] = {"status": "no_fetcher", "date": date}
        updated["raw_news"] = []

    updated["next_node"] = "UPDATE_MARKET_MEMORY"
    return updated

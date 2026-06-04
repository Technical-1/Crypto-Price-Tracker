# news_report.py
import coinlytics.news as _cn


def format_coin_news(coin: str, items: list) -> str:
    """Format news items for a single coin using coinlytics sentiment."""
    sentiment = _cn.sentiment_summary(items)
    lines = [
        f"News: {coin}  [{len(items)} items]  "
        f"sentiment: {sentiment.get('overall', 'neutral')} "
        f"(bullish={sentiment.get('bullish', 0)} bearish={sentiment.get('bearish', 0)})"
    ]
    for item in items[:10]:
        sent = _cn.classify_sentiment(item.get("title", ""))
        marker = {"bullish": "+", "bearish": "-"}.get(sent, " ")
        lines.append(f"  [{marker}] {item.get('published', '')} {item.get('title', '')[:80]}")
    return "\n".join(lines) + "\n"

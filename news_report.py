# news_report.py
import news


def format_coin_news(coin, items, summary, limit=5):
    """Render a coin's news section: header with sentiment summary, then up to
    `limit` headlines (date, sentiment tag, title, URL), or a no-news line."""
    header = "%s - %s (%d up / %d down / %d neutral)" % (
        coin, summary["overall"], summary["bullish"], summary["bearish"],
        summary["neutral"])
    lines = [header, "-" * len(header)]
    if not items:
        lines.append("  (no recent news)")
        return "\n".join(lines)
    for it in items[:limit]:
        tag = news.classify_sentiment(it["title"])
        date = it["published"] or "----------"
        lines.append("  %s  [%-7s]  %s" % (date, tag, it["title"]))
        lines.append("      %s" % it["link"])
    return "\n".join(lines)

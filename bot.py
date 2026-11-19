
import os
import html
import requests
import feedparser
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

HEADERS = {"User-Agent": "HourlyNewsBot/1.0"}

FEEDS = {
    "CRYPTO NEWS": [
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ],
    "TECH NEWS": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
    ],
    "FINANCE NEWS": [
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    ],
}


def get_coingecko_market():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 10,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }

    response = requests.get(
        url, params=params, headers=HEADERS, timeout=20
    )
    response.raise_for_status()

    coins = response.json()
    lines = []

    for coin in coins:
        name = coin["name"]
        symbol = coin["symbol"].upper()
        price = coin.get("current_price") or 0
        change = coin.get("price_change_percentage_24h") or 0

        direction = "🟢" if change >= 0 else "🔴"

        lines.append(
            f"{direction} <b>{symbol}</b> (${price:,.4f}) "
            f"| 24h: {change:+.2f}%"
        )

    return "\n".join(lines)


def get_trending_coins():
    url = "https://api.coingecko.com/api/v3/search/trending"

    response = requests.get(
        url, headers=HEADERS, timeout=20
    )
    response.raise_for_status()

    data = response.json()
    coins = data.get("coins", [])[:7]

    lines = []

    for item in coins:
        coin = item.get("item", {})
        name = coin.get("name", "Unknown")
        symbol = coin.get("symbol", "").upper()
        rank = coin.get("market_cap_rank")

        rank_text = f" | Rank #{rank}" if rank else ""

        lines.append(f"• <b>{name} ({symbol})</b>{rank_text}")

    return "\n".join(lines) if lines else "No trending data available."


def get_news():
    sections = []

    for category, urls in FEEDS.items():
        stories = []
        seen = set()

        for url in urls:
            try:
                feed = feedparser.parse(url)

                for entry in feed.entries[:10]:
                    title = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()

                    if not title or not link or link in seen:
                        continue

                    seen.add(link)

                    published = entry.get("published_parsed")

                    if published:
                        published_time = datetime(
                            *published[:6], tzinfo=timezone.utc
                        )
                        if datetime.now(timezone.utc) - published_time > timedelta(hours=8):
                            continue

                    stories.append(
                        f"• <a href='{html.escape(link, quote=True)}'>"
                        f"{html.escape(title)}</a>"
                    )

                    if len(stories) >= 5:
                        break

            except Exception as error:
                print(f"Feed error: {url} - {error}")

        if stories:
            sections.append(
                f"<b>📰 {category}</b>\n" + "\n".join(stories)
            )
        else:
            sections.append(
                f"<b>📰 {category}</b>\nNo recent headlines retrieved."
            )

    return "\n\n".join(sections)


def send_telegram(message):
    response = requests.post(
        TELEGRAM_URL,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram error: {result}")


def main():
    now = datetime.now(timezone.utc).strftime("%d %b %Y | %H:%M UTC")

    message = f"""
<b>🚨 HOURLY MARKET & NEWS UPDATE</b>
<i>{now}</i>

<b>📊 TOP 10 CRYPTO ASSETS</b>
"""

    try:
        message += get_coingecko_market()
    except Exception as error:
        print(f"Market data error: {error}")
        message += "Market data is temporarily unavailable."

    message += "\n\n<b>🔥 COINGECKO TRENDING COINS</b>\n"

    try:
        message += get_trending_coins()
    except Exception as error:
        print(f"Trending data error: {error}")
        message += "Trending data is temporarily unavailable."

    message += "\n\n" + get_news()

    message += (
        "\n\n<i>Sources: CoinGecko and linked news publishers. "
        "Always do your own research.</i>"
    )

    # Telegram messages have a 4096-character limit.
    if len(message) > 3900:
        message = message[:3850] + "\n\n<i>Message shortened.</i>"

    send_telegram(message)
    print("News update sent successfully.")


if __name__ == "__main__":
    main()

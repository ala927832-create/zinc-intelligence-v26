from unittest.mock import patch

from zincintel.discord import build_discord_payload, send_discord


def snapshot() -> dict:
    return {"market_research":{"close_series":{"latest_close":3010,"sma_14":3000,"sma_30":2975,
        "ema_20":2990,"rsi_14":58,"observations":420,"as_of":"2026-09-14",
        "coverage_start":"2025-01-02","coverage_end":"2026-09-14",
        "source":"westmetall_lme_3m_reference","source_grade":"B_PUBLIC_REFERENCE",
        "trend":{"regime":"BULL","score":45,"persistence_days":4,"risk_level":"NORMAL",
                 "data_confidence":"MEDIUM","reasons":["Close 高於 EMA20"]}}},
        "procurement_state":{"current_inventory_t":99999},
        "investment":{"conservative":{"probability":{"p_profit":.99},"expected_value_usd":99999}}}


def main() -> None:
    payload = build_discord_payload(snapshot())
    text = str(payload)
    for token in ("BULL", "3,010.00", "SMA14", "RSI14", "2026-09-14", "B_PUBLIC_REFERENCE"):
        assert token in text
    for forbidden in ("99999", "p_profit", "expected_value", "Suggested cover", "V2.6"):
        assert forbidden not in text
    with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL":"https://example.invalid/webhook"}), patch("zincintel.discord.requests.post") as post:
        post.return_value.raise_for_status.return_value = None
        assert send_discord(snapshot()) is True
        sent = post.call_args.kwargs["json"]
        assert sent == payload
    print("Discord payload tests passed")


if __name__ == "__main__":
    main()

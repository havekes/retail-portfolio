# ruff: noqa: PLR2004
from src.market.schema import IndicatorCandleSchema
from src.market.service import convert_to_heikin_ashi


def test_heikin_ashi_empty_list():
    assert convert_to_heikin_ashi([]) == []


def test_heikin_ashi_single_candle():
    candle = IndicatorCandleSchema(
        time="2026-01-01",
        open=10.0,
        high=15.0,
        low=8.0,
        close=12.0,
        volume=100.0,
    )
    result = convert_to_heikin_ashi([candle])
    assert len(result) == 1

    ha = result[0]
    assert ha.time == "2026-01-01"
    assert ha.open == (10.0 + 12.0) / 2.0  # 11.0
    assert ha.close == (10.0 + 15.0 + 8.0 + 12.0) / 4.0  # 11.25
    assert ha.high == 15.0
    assert ha.low == 8.0
    assert ha.volume == 100.0


def test_heikin_ashi_sequential_chaining():
    candles = [
        IndicatorCandleSchema(
            time="2026-01-01",
            open=10.0,
            high=15.0,
            low=8.0,
            close=12.0,
            volume=100.0,
        ),
        IndicatorCandleSchema(
            time="2026-01-02",
            open=12.0,
            high=16.0,
            low=11.0,
            close=14.0,
            volume=150.0,
        ),
    ]
    result = convert_to_heikin_ashi(candles)
    assert len(result) == 2

    # First candle
    assert result[0].open == 11.0
    assert result[0].close == 11.25

    # Second candle
    expected_open = (11.0 + 11.25) / 2.0  # 11.125
    expected_close = (12.0 + 16.0 + 11.0 + 14.0) / 4.0  # 13.25
    assert result[1].time == "2026-01-02"
    assert result[1].open == expected_open
    assert result[1].close == expected_close
    assert result[1].high == max(16.0, expected_open, expected_close)
    assert result[1].low == min(11.0, expected_open, expected_close)
    assert result[1].volume == 150.0


def test_heikin_ashi_wicks_expansion():
    # Test case where previous HA values exceed current candle high/low
    candles = [
        IndicatorCandleSchema(
            time=1000,
            open=20.0,
            high=25.0,
            low=18.0,
            close=22.0,
            volume=10.0,
        ),
        IndicatorCandleSchema(
            time=2000,
            open=10.0,
            high=12.0,
            low=9.0,
            close=11.0,
            volume=20.0,
        ),
    ]
    result = convert_to_heikin_ashi(candles)
    # Candle 1: ha_open = 21.0, ha_close = 21.25
    # Candle 2: ha_open = (21.0 + 21.25) / 2 = 21.125
    # Candle 2 raw high is 12.0, but ha_open is 21.125 -> ha_high should be 21.125
    assert result[1].high == 21.125

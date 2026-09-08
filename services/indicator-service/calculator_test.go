package main

import (
	"math"
	"testing"
)

func makeTestCandles(closes []float64, vols []float64) []Candle {
	candles := make([]Candle, len(closes))
	for i, c := range closes {
		v := float64(100)
		if i < len(vols) {
			v = vols[i]
		}
		candles[i] = Candle{
			Time:   i + 1,
			Open:   c,
			High:   c + 1,
			Low:    c - 1,
			Close:  c,
			Volume: v,
		}
	}
	return candles
}

func TestComputeSMA(t *testing.T) {
	candles := makeTestCandles([]float64{10, 20, 30, 40, 50}, nil)

	// Period 3: 3 points expected:
	// idx 2 (time 3): (10+20+30)/3 = 20
	// idx 3 (time 4): (20+30+40)/3 = 30
	// idx 4 (time 5): (30+40+50)/3 = 40
	res := ComputeSMA(candles, 3)
	if len(res) != 3 {
		t.Fatalf("expected 3 points, got %d", len(res))
	}
	if res[0].Value != 20 || res[0].Time != 3 {
		t.Errorf("res[0] = %+v; want time 3, value 20", res[0])
	}
	if res[1].Value != 30 || res[1].Time != 4 {
		t.Errorf("res[1] = %+v; want time 4, value 30", res[1])
	}
	if res[2].Value != 40 || res[2].Time != 5 {
		t.Errorf("res[2] = %+v; want time 5, value 40", res[2])
	}

	// Edge cases: empty candles, period > count, non-positive period
	if len(ComputeSMA(nil, 3)) != 0 {
		t.Errorf("expected empty on nil candles")
	}
	if len(ComputeSMA(candles, 10)) != 0 {
		t.Errorf("expected empty when period > count")
	}
	if len(ComputeSMA(candles, 0)) != 0 {
		t.Errorf("expected empty when period == 0")
	}
	if len(ComputeSMA(candles, -1)) != 0 {
		t.Errorf("expected empty when period < 0")
	}
}

func TestComputeEMA(t *testing.T) {
	candles := makeTestCandles([]float64{10, 20, 30, 40, 50}, nil)
	res := ComputeEMA(candles, 3)

	if len(res) != 3 {
		t.Fatalf("expected 3 points, got %d", len(res))
	}
	// Initial EMA is SMA: (10+20+30)/3 = 20
	if res[0].Value != 20 || res[0].Time != 3 {
		t.Errorf("res[0] = %+v; want time 3, value 20", res[0])
	}
	// Multiplier = 2 / (3 + 1) = 0.5
	// EMA(40) = (40 - 20) * 0.5 + 20 = 30
	if res[1].Value != 30 || res[1].Time != 4 {
		t.Errorf("res[1] = %+v; want time 4, value 30", res[1])
	}
	// EMA(50) = (50 - 30) * 0.5 + 30 = 40
	if res[2].Value != 40 || res[2].Time != 5 {
		t.Errorf("res[2] = %+v; want time 5, value 40", res[2])
	}

	// Edge cases
	if len(ComputeEMA(nil, 3)) != 0 {
		t.Errorf("expected empty on nil candles")
	}
	if len(ComputeEMA(candles, 10)) != 0 {
		t.Errorf("expected empty when period > count")
	}
}

func TestComputeBB(t *testing.T) {
	candles := makeTestCandles([]float64{10, 20, 30, 40, 50}, nil)
	res := ComputeBB(candles, 3, 2.0)

	if len(res) != 3 {
		t.Fatalf("expected 3 points, got %d", len(res))
	}

	for i, pt := range res {
		if pt.Upper <= pt.Middle {
			t.Errorf("[%d] upper %f <= middle %f", i, pt.Upper, pt.Middle)
		}
		if pt.Lower >= pt.Middle {
			t.Errorf("[%d] lower %f >= middle %f", i, pt.Lower, pt.Middle)
		}
		if math.IsNaN(pt.Upper) || math.IsNaN(pt.Middle) || math.IsNaN(pt.Lower) {
			t.Errorf("[%d] contains NaN: %+v", i, pt)
		}
	}

	// Edge cases
	if len(ComputeBB(nil, 3, 2.0)) != 0 {
		t.Errorf("expected empty on nil candles")
	}
	if len(ComputeBB(candles, 10, 2.0)) != 0 {
		t.Errorf("expected empty when period > count")
	}
}

func TestComputeMACD(t *testing.T) {
	closes := make([]float64, 40)
	for i := range closes {
		closes[i] = float64(100 + i*2)
	}
	candles := makeTestCandles(closes, nil)
	res := ComputeMACD(candles, 12, 26, 9)

	if len(res) == 0 {
		t.Fatalf("expected MACD points, got 0")
	}

	for i, pt := range res {
		diff := math.Abs((pt.MACD - pt.Signal) - pt.Histogram)
		if diff > 1e-9 {
			t.Errorf("[%d] histogram %f != macd - signal (%f - %f = %f)",
				i, pt.Histogram, pt.MACD, pt.Signal, pt.MACD-pt.Signal)
		}
		if math.IsNaN(pt.MACD) || math.IsNaN(pt.Signal) || math.IsNaN(pt.Histogram) {
			t.Errorf("[%d] contains NaN: %+v", i, pt)
		}
	}

	// Insufficient candles
	shortCandles := makeTestCandles([]float64{10, 20, 30}, nil)
	if len(ComputeMACD(shortCandles, 12, 26, 9)) != 0 {
		t.Errorf("expected empty when candles <= idle period")
	}
}

func TestComputeRSI(t *testing.T) {
	closes := make([]float64, 30)
	for i := range closes {
		closes[i] = float64(10 + i)
	}
	candles := makeTestCandles(closes, nil)
	res := ComputeRSI(candles, 14)

	if len(res) == 0 {
		t.Fatalf("expected RSI points, got 0")
	}

	for i, pt := range res {
		if pt.Value < 0 || pt.Value > 100 {
			t.Errorf("[%d] RSI out of [0, 100] range: %f", i, pt.Value)
		}
		if pt.Value != pt.RSI {
			t.Errorf("[%d] RSI value %f != RSI field %f", i, pt.Value, pt.RSI)
		}
		if math.IsNaN(pt.Value) {
			t.Errorf("[%d] contains NaN: %+v", i, pt)
		}
	}

	// Insufficient candles
	shortCandles := makeTestCandles([]float64{10, 20}, nil)
	if len(ComputeRSI(shortCandles, 14)) != 0 {
		t.Errorf("expected empty when candles <= period")
	}
}

func TestComputeOBV(t *testing.T) {
	closes := []float64{10, 12, 11, 15}
	vols := []float64{100, 200, 150, 300}
	candles := makeTestCandles(closes, vols)

	res := ComputeOBV(candles)
	if len(res) != 4 {
		t.Fatalf("expected 4 OBV points, got %d", len(res))
	}

	// Bar 0: initial volume = 100
	if res[0].Value != 100 {
		t.Errorf("res[0] = %f; want 100", res[0].Value)
	}
	// Bar 1: close 12 > 10 -> +200 = 300
	if res[1].Value != 300 {
		t.Errorf("res[1] = %f; want 300", res[1].Value)
	}
	// Bar 2: close 11 < 12 -> -150 = 150
	if res[2].Value != 150 {
		t.Errorf("res[2] = %f; want 150", res[2].Value)
	}
	// Bar 3: close 15 > 11 -> +300 = 450
	if res[3].Value != 450 {
		t.Errorf("res[3] = %f; want 450", res[3].Value)
	}

	// Empty candles
	if len(ComputeOBV(nil)) != 0 {
		t.Errorf("expected empty on nil candles")
	}
}

func TestComputeIndicatorTimeframeMA(t *testing.T) {
	// 15 candles on 1h interval with 2-day MA -> scaled period = 2 * 7 = 14
	// 15 candles with period 14 -> 2 points (len - 14 + 1 = 2)
	closes := make([]float64, 15)
	for i := range closes {
		closes[i] = float64((i + 1) * 10)
	}
	candles := makeTestCandles(closes, nil)

	spec := IndicatorSpec{
		Type:   "ma50",
		Period: 2,
	}
	result, err := ComputeIndicator(candles, spec, "1h")
	if err != nil {
		t.Fatalf("ComputeIndicator failed: %v", err)
	}

	maPoints, ok := result.([]MAPoint)
	if !ok {
		t.Fatalf("expected []MAPoint, got %T", result)
	}
	if len(maPoints) != 2 {
		t.Fatalf("expected 2 points, got %d", len(maPoints))
	}
	// Points should be at index 13 and 14
	// sum(1..14)*10 / 14 = (14*15/2)*10 / 14 = 75
	// sum(2..15)*10 / 14 = (15*16/2 - 1)*10 / 14 = 85
	if maPoints[0].Value != 75 {
		t.Errorf("maPoints[0].Value = %f; want 75", maPoints[0].Value)
	}
	if maPoints[1].Value != 85 {
		t.Errorf("maPoints[1].Value = %f; want 85", maPoints[1].Value)
	}
}

func TestComputeIndicatorSettingsFallback(t *testing.T) {
	candles := makeTestCandles([]float64{10, 20, 30, 40, 50}, nil)

	spec := IndicatorSpec{
		Type: "sma",
		Settings: map[string]any{
			"period": 2,
		},
	}
	result, err := ComputeIndicator(candles, spec, "1d")
	if err != nil {
		t.Fatalf("ComputeIndicator failed: %v", err)
	}
	maPoints := result.([]MAPoint)
	if len(maPoints) != 4 {
		t.Fatalf("expected 4 points with period 2, got %d", len(maPoints))
	}
	if maPoints[0].Value != 15 {
		t.Errorf("maPoints[0].Value = %f; want 15", maPoints[0].Value)
	}
}

func TestComputeIndicatorUnsupportedType(t *testing.T) {
	candles := makeTestCandles([]float64{10, 20}, nil)
	spec := IndicatorSpec{Type: "invalid_indicator"}
	_, err := ComputeIndicator(candles, spec, "1d")
	if err == nil {
		t.Fatalf("expected error for unsupported indicator type")
	}
}

package main

import (
	"fmt"
	"math"
	"strings"
	"sync"

	"github.com/cinar/indicator/v2/helper"
	"github.com/cinar/indicator/v2/momentum"
	"github.com/cinar/indicator/v2/trend"
	"github.com/cinar/indicator/v2/volatility"
	"github.com/cinar/indicator/v2/volume"
)

// ComputeIndicator computes an indicator series according to the spec and chart interval.
func ComputeIndicator(candles []Candle, spec IndicatorSpec, interval string) (any, error) {
	normType := strings.ToLower(strings.TrimSpace(spec.Type))

	switch normType {
	case "ma50", "ma_50", "ma_50_day", "50ma":
		period := spec.GetPeriod(50)
		scaled := ScalePeriod(period, interval, UnitDay)
		return ComputeSMA(candles, scaled), nil

	case "ma200", "ma_200", "ma_200_day", "200ma":
		period := spec.GetPeriod(200)
		scaled := ScalePeriod(period, interval, UnitDay)
		return ComputeSMA(candles, scaled), nil

	case "ma50w", "ma_50w", "ma_50_week", "50wma":
		period := spec.GetPeriod(50)
		scaled := ScalePeriod(period, interval, UnitWeek)
		return ComputeSMA(candles, scaled), nil

	case "ma200w", "ma_200w", "ma_200_week", "200wma":
		period := spec.GetPeriod(200)
		scaled := ScalePeriod(period, interval, UnitWeek)
		return ComputeSMA(candles, scaled), nil

	case "sma":
		period := spec.GetPeriod(14)
		return ComputeSMA(candles, period), nil

	case "ema":
		period := spec.GetPeriod(14)
		return ComputeEMA(candles, period), nil

	case "bb", "bollinger", "bollinger_bands":
		period := spec.GetPeriod(20)
		stdDev := spec.GetStdDev(2.0)
		return ComputeBB(candles, period, stdDev), nil

	case "macd":
		fast := spec.GetFast(12)
		slow := spec.GetSlow(26)
		signal := spec.GetSignal(9)
		return ComputeMACD(candles, fast, slow, signal), nil

	case "rsi":
		period := spec.GetPeriod(14)
		return ComputeRSI(candles, period), nil

	case "obv":
		return ComputeOBV(candles), nil

	default:
		return nil, fmt.Errorf("unsupported indicator type: %s", spec.Type)
	}
}

// ComputeSMA calculates Simple Moving Average.
func ComputeSMA(candles []Candle, period int) []MAPoint {
	if len(candles) < period || period <= 0 {
		return []MAPoint{}
	}

	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}

	sma := trend.NewSmaWithPeriod[float64](period)
	res := helper.ChanToSlice(sma.Compute(helper.SliceToChan(closes)))

	startIdx := len(candles) - len(res)
	points := make([]MAPoint, 0, len(res))
	for i, val := range res {
		if math.IsNaN(val) || math.IsInf(val, 0) {
			continue
		}
		points = append(points, MAPoint{
			Time:  candles[startIdx+i].Time,
			Value: val,
		})
	}
	return points
}

// ComputeEMA calculates Exponential Moving Average.
func ComputeEMA(candles []Candle, period int) []MAPoint {
	if len(candles) < period || period <= 0 {
		return []MAPoint{}
	}

	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}

	ema := trend.NewEmaWithPeriod[float64](period)
	res := helper.ChanToSlice(ema.Compute(helper.SliceToChan(closes)))

	startIdx := len(candles) - len(res)
	points := make([]MAPoint, 0, len(res))
	for i, val := range res {
		if math.IsNaN(val) || math.IsInf(val, 0) {
			continue
		}
		points = append(points, MAPoint{
			Time:  candles[startIdx+i].Time,
			Value: val,
		})
	}
	return points
}

// ComputeBB calculates Bollinger Bands with upper, middle, and lower bands.
func ComputeBB(candles []Candle, period int, stdDev float64) []BBPoint {
	if len(candles) < period || period <= 0 {
		return []BBPoint{}
	}

	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}

	bb := volatility.NewBollingerBandsWithPeriod[float64](period)
	bb.Multiplier = stdDev

	upperChan, midChan, lowerChan := bb.Compute(helper.SliceToChan(closes))

	var upper, mid, lower []float64
	var wg sync.WaitGroup
	wg.Add(3)
	go func() { defer wg.Done(); upper = helper.ChanToSlice(upperChan) }()
	go func() { defer wg.Done(); mid = helper.ChanToSlice(midChan) }()
	go func() { defer wg.Done(); lower = helper.ChanToSlice(lowerChan) }()
	wg.Wait()

	count := len(mid)
	if len(upper) < count {
		count = len(upper)
	}
	if len(lower) < count {
		count = len(lower)
	}
	if count == 0 {
		return []BBPoint{}
	}

	startIdx := len(candles) - count
	points := make([]BBPoint, 0, count)
	for i := 0; i < count; i++ {
		u := upper[i]
		m := mid[i]
		l := lower[i]
		if math.IsNaN(u) || math.IsInf(u, 0) ||
			math.IsNaN(m) || math.IsInf(m, 0) ||
			math.IsNaN(l) || math.IsInf(l, 0) {
			continue
		}
		points = append(points, BBPoint{
			Time:   candles[startIdx+i].Time,
			Middle: m,
			Upper:  u,
			Lower:  l,
		})
	}
	return points
}

// ComputeMACD calculates MACD, Signal, and Histogram.
func ComputeMACD(candles []Candle, fast, slow, signal int) []MACDPoint {
	if fast <= 0 || slow <= 0 || signal <= 0 {
		return []MACDPoint{}
	}

	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}

	macd := trend.NewMacdWithPeriod[float64](fast, slow, signal)
	if len(candles) <= macd.IdlePeriod() {
		return []MACDPoint{}
	}

	macdChan, sigChan := macd.Compute(helper.SliceToChan(closes))

	var macdLine, sigLine []float64
	var wg sync.WaitGroup
	wg.Add(2)
	go func() { defer wg.Done(); macdLine = helper.ChanToSlice(macdChan) }()
	go func() { defer wg.Done(); sigLine = helper.ChanToSlice(sigChan) }()
	wg.Wait()

	count := len(macdLine)
	if len(sigLine) < count {
		count = len(sigLine)
	}
	if count == 0 {
		return []MACDPoint{}
	}

	startIdx := len(candles) - count
	points := make([]MACDPoint, 0, count)
	for i := 0; i < count; i++ {
		m := macdLine[i]
		s := sigLine[i]
		h := m - s
		if math.IsNaN(m) || math.IsInf(m, 0) ||
			math.IsNaN(s) || math.IsInf(s, 0) ||
			math.IsNaN(h) || math.IsInf(h, 0) {
			continue
		}
		points = append(points, MACDPoint{
			Time:      candles[startIdx+i].Time,
			MACD:      m,
			Signal:    s,
			Histogram: h,
		})
	}
	return points
}

// ComputeRSI calculates Relative Strength Index.
func ComputeRSI(candles []Candle, period int) []RSIPoint {
	if len(candles) <= period || period <= 0 {
		return []RSIPoint{}
	}

	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}

	rsi := momentum.NewRsiWithPeriod[float64](period)
	res := helper.ChanToSlice(rsi.Compute(helper.SliceToChan(closes)))

	startIdx := len(candles) - len(res)
	points := make([]RSIPoint, 0, len(res))
	for i, val := range res {
		if math.IsNaN(val) || math.IsInf(val, 0) {
			continue
		}
		points = append(points, RSIPoint{
			Time:  candles[startIdx+i].Time,
			Value: val,
			RSI:   val,
		})
	}
	return points
}

// ComputeOBV calculates On-Balance Volume.
func ComputeOBV(candles []Candle) []OBVPoint {
	if len(candles) == 0 {
		return []OBVPoint{}
	}

	closes := make([]float64, len(candles))
	vols := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
		vols[i] = c.Volume
	}

	obv := volume.NewObv[float64]()
	res := helper.ChanToSlice(obv.Compute(helper.SliceToChan(closes), helper.SliceToChan(vols)))

	startIdx := len(candles) - len(res)
	points := make([]OBVPoint, 0, len(res))
	for i, val := range res {
		if math.IsNaN(val) || math.IsInf(val, 0) {
			continue
		}
		points = append(points, OBVPoint{
			Time:  candles[startIdx+i].Time,
			Value: val,
		})
	}
	return points
}

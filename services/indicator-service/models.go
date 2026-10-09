package main

import (
	"encoding/json"
	"fmt"
	"math"
	"strconv"
)

const (
	maxIndicators  = 32
	maxCandles     = 50000
	minPeriodParam = 1
	maxPeriodParam = 1000
	minStdDev      = 0.0
	maxStdDev      = 10.0
)

// Candle represents an OHLCV candle.
type Candle struct {
	Time   any     `json:"time"`
	Open   float64 `json:"open"`
	High   float64 `json:"high"`
	Low    float64 `json:"low"`
	Close  float64 `json:"close"`
	Volume float64 `json:"volume"`
}

// IndicatorSpec describes an indicator calculation request.
type IndicatorSpec struct {
	ID       string         `json:"id,omitempty"`
	Type     string         `json:"type"`
	Period   int            `json:"period,omitempty"`
	Fast     int            `json:"fast,omitempty"`
	Slow     int            `json:"slow,omitempty"`
	Signal   int            `json:"signal,omitempty"`
	StdDev   float64        `json:"stdDev,omitempty"`
	Settings map[string]any `json:"settings,omitempty"`
}

// ResultKey returns the key to use in the output response (ID if set, else Type).
func (s *IndicatorSpec) ResultKey() string {
	if s.ID != "" {
		return s.ID
	}
	return s.Type
}

func toInt(v any) int {
	switch val := v.(type) {
	case int:
		return val
	case int64:
		return int(val)
	case float64:
		return int(val)
	case json.Number:
		if i, err := val.Int64(); err == nil {
			return int(i)
		}
		if f, err := val.Float64(); err == nil {
			return int(f)
		}
	case string:
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return 0
}

func toFloat64(v any) float64 {
	switch val := v.(type) {
	case float64:
		return val
	case int:
		return float64(val)
	case int64:
		return float64(val)
	case json.Number:
		if f, err := val.Float64(); err == nil {
			return f
		}
	case string:
		if f, err := strconv.ParseFloat(val, 64); err == nil {
			return f
		}
	}
	return 0
}

// GetPeriod retrieves the period from the spec or its settings map, falling back to defaultValue.
func (s *IndicatorSpec) GetPeriod(fallback int) int {
	if s.Period > 0 {
		return s.Period
	}
	if s.Settings != nil {
		if v, ok := s.Settings["period"]; ok {
			if val := toInt(v); val > 0 {
				return val
			}
		}
	}
	return fallback
}

// GetFast retrieves the fast period from the spec or its settings map, falling back to defaultValue.
func (s *IndicatorSpec) GetFast(fallback int) int {
	if s.Fast > 0 {
		return s.Fast
	}
	if s.Settings != nil {
		if v, ok := s.Settings["fast"]; ok {
			if val := toInt(v); val > 0 {
				return val
			}
		}
	}
	return fallback
}

// GetSlow retrieves the slow period from the spec or its settings map, falling back to defaultValue.
func (s *IndicatorSpec) GetSlow(fallback int) int {
	if s.Slow > 0 {
		return s.Slow
	}
	if s.Settings != nil {
		if v, ok := s.Settings["slow"]; ok {
			if val := toInt(v); val > 0 {
				return val
			}
		}
	}
	return fallback
}

// GetSignal retrieves the signal period from the spec or its settings map, falling back to defaultValue.
func (s *IndicatorSpec) GetSignal(fallback int) int {
	if s.Signal > 0 {
		return s.Signal
	}
	if s.Settings != nil {
		if v, ok := s.Settings["signal"]; ok {
			if val := toInt(v); val > 0 {
				return val
			}
		}
	}
	return fallback
}

// GetStdDev retrieves the standard deviation multiplier from the spec or its settings map, falling back to defaultValue.
func (s *IndicatorSpec) GetStdDev(fallback float64) float64 {
	if s.StdDev > 0 {
		return s.StdDev
	}
	if s.Settings != nil {
		if v, ok := s.Settings["stdDev"]; ok {
			if val := toFloat64(v); val > 0 {
				return val
			}
		}
	}
	return fallback
}

// validate checks that the indicator spec parameters are within allowable bounds.
func (s *IndicatorSpec) validate() error {
	period := s.GetPeriod(1)
	if period < minPeriodParam {
		return fmt.Errorf("indicator %s: period %d must be at least %d", s.ResultKey(), period, minPeriodParam)
	}
	if period > maxPeriodParam {
		return fmt.Errorf("indicator %s: period %d exceeds limit of %d", s.ResultKey(), period, maxPeriodParam)
	}

	fast := s.GetFast(1)
	if fast < minPeriodParam {
		return fmt.Errorf("indicator %s: fast %d must be at least %d", s.ResultKey(), fast, minPeriodParam)
	}
	if fast > maxPeriodParam {
		return fmt.Errorf("indicator %s: fast %d exceeds limit of %d", s.ResultKey(), fast, maxPeriodParam)
	}

	slow := s.GetSlow(1)
	if slow < minPeriodParam {
		return fmt.Errorf("indicator %s: slow %d must be at least %d", s.ResultKey(), slow, minPeriodParam)
	}
	if slow > maxPeriodParam {
		return fmt.Errorf("indicator %s: slow %d exceeds limit of %d", s.ResultKey(), slow, maxPeriodParam)
	}

	signal := s.GetSignal(1)
	if signal < minPeriodParam {
		return fmt.Errorf("indicator %s: signal %d must be at least %d", s.ResultKey(), signal, minPeriodParam)
	}
	if signal > maxPeriodParam {
		return fmt.Errorf("indicator %s: signal %d exceeds limit of %d", s.ResultKey(), signal, maxPeriodParam)
	}

	stdDev := s.GetStdDev(2.0)
	if stdDev <= minStdDev || math.IsNaN(stdDev) {
		return fmt.Errorf("indicator %s: stdDev %v must be greater than 0", s.ResultKey(), stdDev)
	}
	if stdDev > maxStdDev || math.IsInf(stdDev, 0) {
		return fmt.Errorf("indicator %s: stdDev %v exceeds limit of %v", s.ResultKey(), stdDev, maxStdDev)
	}

	return nil
}

// MAPoint represents a single moving average point aligned with candle time.
type MAPoint struct {
	Time  any     `json:"time"`
	Value float64 `json:"value"`
}

// BBPoint represents a Bollinger Bands point aligned with candle time.
type BBPoint struct {
	Time   any     `json:"time"`
	Middle float64 `json:"middle"`
	Upper  float64 `json:"upper"`
	Lower  float64 `json:"lower"`
}

// MACDPoint represents a MACD point aligned with candle time.
type MACDPoint struct {
	Time      any     `json:"time"`
	MACD      float64 `json:"macd"`
	Signal    float64 `json:"signal"`
	Histogram float64 `json:"histogram"`
}

// RSIPoint represents an RSI point aligned with candle time.
type RSIPoint struct {
	Time  any     `json:"time"`
	Value float64 `json:"value"`
	RSI   float64 `json:"rsi,omitempty"`
}

// OBVPoint represents an On-Balance Volume point aligned with candle time.
type OBVPoint struct {
	Time  any     `json:"time"`
	Value float64 `json:"value"`
}

// ComputeRequest is the payload for POST /compute.
type ComputeRequest struct {
	Interval   string          `json:"interval"`
	Candles    []Candle        `json:"candles"`
	Indicators []IndicatorSpec `json:"indicators"`
}

// ComputeResponse is the response payload for POST /compute.
type ComputeResponse struct {
	Indicators map[string]any `json:"indicators"`
}

// HealthResponse is the payload for GET /health.
type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
}

// ErrorResponse represents a JSON error response.
type ErrorResponse struct {
	Error string `json:"error"`
}

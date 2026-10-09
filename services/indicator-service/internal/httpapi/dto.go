package httpapi

import (
	"fmt"
	"retail-portfolio/services/indicator-service/internal/indicators"
)

const (
	maxIndicators = 32
	maxCandles    = 50000
)

// ComputeRequest is the payload for POST /compute.
type ComputeRequest struct {
	Interval   string                     `json:"interval"`
	Candles    []indicators.Candle        `json:"candles"`
	Indicators []indicators.IndicatorSpec `json:"indicators"`
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

// validateComputeRequest validates bounds for POST /compute payloads before computation.
func validateComputeRequest(req ComputeRequest) error {
	if len(req.Indicators) > maxIndicators {
		return fmt.Errorf("indicators count %d exceeds limit of %d", len(req.Indicators), maxIndicators)
	}
	if len(req.Candles) > maxCandles {
		return fmt.Errorf("candles count %d exceeds limit of %d", len(req.Candles), maxCandles)
	}
	for i := range req.Indicators {
		if err := req.Indicators[i].Validate(); err != nil {
			return err
		}
	}
	return nil
}

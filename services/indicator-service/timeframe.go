package main

import (
	"math"
	"strings"
)

// TimeframeMAUnit defines whether the moving average period is based on days or weeks.
type TimeframeMAUnit string

const (
	UnitDay  TimeframeMAUnit = "day"
	UnitWeek TimeframeMAUnit = "week"
)

// ScalePeriod scales a moving average period according to the chart interval and unit.
// Intervals supported: "1h", "4h", "1d", "1w", "1m" (case-insensitive).
//
// Day MA (unit: 'day'):
//   - 1h -> period * 7
//   - 4h -> period * 2
//   - 1d -> period
//   - 1w -> round(period / 5) (minimum 1)
//   - 1m -> round(period / 21) (minimum 1)
//
// Week MA (unit: 'week'):
//   - 1h -> period * 35
//   - 4h -> period * 10
//   - 1d -> period * 5
//   - 1w -> period
//   - 1m -> round(period * 12 / 52) (minimum 1)
func ScalePeriod(period int, interval string, unit TimeframeMAUnit) int {
	if period <= 0 {
		return 0
	}

	normInterval := strings.ToLower(strings.TrimSpace(interval))

	if unit == UnitWeek {
		switch normInterval {
		case "1h":
			return period * 35
		case "4h":
			return period * 10
		case "1d":
			return period * 5
		case "1w":
			return period
		case "1m":
			return int(math.Max(1, math.Round(float64(period)*12.0/52.0)))
		default:
			return period
		}
	}

	// Default: unit == UnitDay
	switch normInterval {
	case "1h":
		return period * 7
	case "4h":
		return period * 2
	case "1d":
		return period
	case "1w":
		return int(math.Max(1, math.Round(float64(period)/5.0)))
	case "1m":
		return int(math.Max(1, math.Round(float64(period)/21.0)))
	default:
		return period
	}
}

package main

import (
	"testing"
)

func TestScalePeriod(t *testing.T) {
	tests := []struct {
		name     string
		period   int
		interval string
		unit     TimeframeMAUnit
		expected int
	}{
		// Zero or negative periods
		{"zero period day", 0, "1d", UnitDay, 0},
		{"negative period week", -5, "1h", UnitWeek, 0},

		// Day MA scaling
		{"day ma 1h (2 days)", 2, "1h", UnitDay, 14},
		{"day ma 1h (50 days)", 50, "1h", UnitDay, 350},
		{"day ma 4h (2 days)", 2, "4h", UnitDay, 4},
		{"day ma 4h (50 days)", 50, "4h", UnitDay, 100},
		{"day ma 1d (50 days)", 50, "1d", UnitDay, 50},
		{"day ma 1d (200 days)", 200, "1d", UnitDay, 200},
		{"day ma 1w (10 days)", 10, "1w", UnitDay, 2},
		{"day ma 1w (50 days)", 50, "1w", UnitDay, 10},
		{"day ma 1w (200 days)", 200, "1w", UnitDay, 40},
		{"day ma 1w (2 days minimum 1)", 2, "1w", UnitDay, 1},
		{"day ma 1m (21 days)", 21, "1m", UnitDay, 1},
		{"day ma 1m (50 days)", 50, "1m", UnitDay, 2},
		{"day ma 1m (200 days)", 200, "1m", UnitDay, 10},
		{"day ma 1m (5 days minimum 1)", 5, "1m", UnitDay, 1},
		{"day ma unknown interval", 50, "custom", UnitDay, 50},

		// Week MA scaling
		{"week ma 1h (2 weeks)", 2, "1h", UnitWeek, 70},
		{"week ma 1h (50 weeks)", 50, "1h", UnitWeek, 1750},
		{"week ma 4h (2 weeks)", 2, "4h", UnitWeek, 20},
		{"week ma 4h (50 weeks)", 50, "4h", UnitWeek, 500},
		{"week ma 1d (2 weeks)", 2, "1d", UnitWeek, 10},
		{"week ma 1d (50 weeks)", 50, "1d", UnitWeek, 250},
		{"week ma 1w (50 weeks)", 50, "1w", UnitWeek, 50},
		{"week ma 1w (200 weeks)", 200, "1w", UnitWeek, 200},
		{"week ma 1m (4 weeks)", 4, "1m", UnitWeek, 1},
		{"week ma 1m (50 weeks)", 50, "1m", UnitWeek, 12},
		{"week ma 1m (200 weeks)", 200, "1m", UnitWeek, 46},
		{"week ma 1m (1 week minimum 1)", 1, "1m", UnitWeek, 1},
		{"week ma unknown interval", 50, "unknown", UnitWeek, 50},

		// Case-insensitivity & whitespace trimming
		{"case insensitive 1H", 2, " 1H ", UnitDay, 14},
		{"case insensitive 1W", 50, "1W", UnitWeek, 50},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ScalePeriod(tt.period, tt.interval, tt.unit)
			if got != tt.expected {
				t.Errorf("ScalePeriod(%d, %q, %q) = %d; want %d",
					tt.period, tt.interval, tt.unit, got, tt.expected)
			}
		})
	}
}

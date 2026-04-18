## ADDED Requirements

### Requirement: Moving average indicators
The system SHALL support 50-day, 200-day, 50-week, and 200-week moving average indicators.

#### Scenario: 50-day MA toggle
- **WHEN** user toggles 50-day MA indicator
- **THEN** the indicator line is calculated and displayed on the chart
- **THEN** the indicator appears in the chart legend with color coding

#### Scenario: 200-day MA toggle
- **WHEN** user toggles 200-day MA indicator
- **THEN** the indicator line is calculated and displayed on the chart
- **THEN** the indicator appears in the chart legend with color coding

#### Scenario: 50-week MA toggle
- **WHEN** user toggles 50-week MA indicator
- **THEN** the indicator line is calculated using weekly close prices
- **THEN** the indicator appears on the chart with distinct styling

#### Scenario: 200-week MA toggle
- **WHEN** user toggles 200-week MA indicator
- **THEN** the indicator line is calculated using weekly close prices
- **THEN** the indicator appears on the chart with distinct styling

#### Scenario: Multiple MAs active
- **WHEN** multiple moving averages are active simultaneously
- **THEN** all selected MAs display on the chart with unique colors
- **THEN** the legend shows all active indicators

### Requirement: MACD indicator
The system SHALL support Moving Average Convergence Divergence (MACD) indicator.

#### Scenario: MACD toggle
- **WHEN** user toggles MACD indicator
- **THEN** a separate indicator panel displays MACD line, signal line, and histogram
- **THEN** the indicator panel is positioned below the main price chart

#### Scenario: MACD calculation
- **WHEN** MACD is active
- **THEN** the system calculates MACD using default 12/26/9 parameters
- **THEN** crossovers are visually indicated on the histogram

### Requirement: RSI indicator
The system SHALL support Relative Strength Index (RSI) indicator.

#### Scenario: RSI toggle
- **WHEN** user toggles RSI indicator
- **THEN** a separate indicator panel displays RSI line
- **THEN** overbought (70) and oversold (30) levels are marked

#### Scenario: RSI calculation
- **WHEN** RSI is active
- **THEN** the system calculates RSI using default 14-period setting
- **THEN** the RSI line oscillates between 0 and 100

### Requirement: Indicator persistence
The system SHALL remember user's indicator preferences per security.

#### Scenario: Return to security
- **WHEN** user navigates away and returns to the same security
- **THEN** previously enabled indicators are restored
- **THEN** indicator settings and styling are preserved

#### Scenario: New security
- **WHEN** user navigates to a different security
- **THEN** that security's saved indicators are loaded
- **THEN** if no saved preferences exist, defaults are shown

### Requirement: Indicator performance
The system SHALL calculate and display indicators efficiently.

#### Scenario: Large dataset
- **WHEN** security has extensive historical data
- **THEN** indicators calculate within acceptable time (<500ms)
- **THEN** chart remains responsive during calculation

#### Scenario: Real-time updates
- **WHEN** new price data arrives
- **THEN** active indicators update incrementally
- **THEN** full recalculation is not required

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import IndicatorHelpModal from './indicator-help-modal.svelte';

describe('IndicatorHelpModal Component', () => {
	it('renders MACD help information when indicatorId is macd', () => {
		render(IndicatorHelpModal, {
			props: { open: true, indicatorId: 'macd' }
		});

		expect(screen.getByText('Moving Average Convergence Divergence (MACD)')).toBeInTheDocument();
		expect(screen.getByText('Momentum & Trend-Following Indicator')).toBeInTheDocument();
		expect(
			screen.getByText(/MACD tracks the relationship between two exponential moving averages/)
		).toBeInTheDocument();
		expect(screen.getByText('MACD Line:')).toBeInTheDocument();
		expect(screen.getByText('Signal Line:')).toBeInTheDocument();
		expect(screen.getByText('Histogram:')).toBeInTheDocument();
	});

	it('renders Bollinger Bands help information when indicatorId is bb', () => {
		render(IndicatorHelpModal, {
			props: { open: true, indicatorId: 'bb' }
		});

		expect(screen.getByText('Bollinger Bands')).toBeInTheDocument();
		expect(screen.getByText('Volatility & Range Channel Indicator')).toBeInTheDocument();
		expect(
			screen.getByText(/Bollinger Bands consist of a center Simple Moving Average/)
		).toBeInTheDocument();
		expect(screen.getByText('Middle Band:')).toBeInTheDocument();
		expect(screen.getByText('Upper Band:')).toBeInTheDocument();
		expect(screen.getByText('Lower Band:')).toBeInTheDocument();
	});

	it('renders RSI help information when indicatorId is rsi', () => {
		render(IndicatorHelpModal, {
			props: { open: true, indicatorId: 'rsi' }
		});

		expect(screen.getByText('Relative Strength Index (RSI)')).toBeInTheDocument();
		expect(screen.getByText('Momentum Oscillator (0 to 100)')).toBeInTheDocument();
		expect(
			screen.getByText(/RSI measures the speed and change of price movements/)
		).toBeInTheDocument();
		expect(screen.getByText('Overbought Level (70):')).toBeInTheDocument();
		expect(screen.getByText('Oversold Level (30):')).toBeInTheDocument();
	});

	it('renders OBV help information when indicatorId is obv', () => {
		render(IndicatorHelpModal, {
			props: { open: true, indicatorId: 'obv' }
		});

		expect(screen.getByText('On-Balance Volume (OBV)')).toBeInTheDocument();
		expect(screen.getByText('Cumulative Volume Flow Momentum')).toBeInTheDocument();
		expect(
			screen.getByText(/On-Balance Volume is a cumulative momentum indicator/)
		).toBeInTheDocument();
		expect(screen.getByText('Cumulative Volume Line:')).toBeInTheDocument();
	});

	it('renders fallback title when indicatorId is null or unknown', () => {
		render(IndicatorHelpModal, {
			props: { open: true, indicatorId: null }
		});

		expect(screen.getByText('Indicator Information')).toBeInTheDocument();
	});
});

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import StockLogo, { getMonogram } from './stock-logo.svelte';

describe('getMonogram', () => {
	it('returns single letter for 1-char tickers', () => {
		expect(getMonogram('C')).toBe('C');
		expect(getMonogram('F')).toBe('F');
	});

	it('returns two letters for 2-char tickers', () => {
		expect(getMonogram('BA')).toBe('BA');
		expect(getMonogram('RY')).toBe('RY');
	});

	it('returns first two letters for multi-character tickers', () => {
		expect(getMonogram('AAPL')).toBe('AA');
		expect(getMonogram('GOOGL')).toBe('GO');
		expect(getMonogram('MSFT')).toBe('MS');
	});

	it('strips exchange suffixes before generating monogram', () => {
		expect(getMonogram('TD.TO')).toBe('TD');
		expect(getMonogram('ABC.V')).toBe('AB');
		expect(getMonogram('VOD.L')).toBe('VO');
		expect(getMonogram('BRK-B')).toBe('BR');
	});

	it('handles empty or whitespace strings gracefully', () => {
		expect(getMonogram('')).toBe('');
		expect(getMonogram('   ')).toBe('');
	});
});

describe('StockLogo Component', () => {
	it('renders image pointing to the backend logo endpoint', () => {
		render(StockLogo, {
			props: {
				securityId: 'sec-123',
				symbol: 'AAPL'
			}
		});

		const img = screen.getByRole('img');
		expect(img).toBeInTheDocument();
		expect(img).toHaveAttribute('src', '/api/v1/market/securities/sec-123/logo');
		expect(img).toHaveAttribute('alt', 'AAPL logo');
	});

	it('shows monogram fallback when image fails to load (error event)', async () => {
		render(StockLogo, {
			props: {
				securityId: 'sec-123',
				symbol: 'AAPL'
			}
		});

		const img = screen.getByRole('img');
		await fireEvent.error(img);

		const fallback = screen.getByTestId('stock-logo-fallback');
		expect(fallback).toBeInTheDocument();
		expect(fallback).toHaveTextContent('AA');
		expect(screen.queryByRole('img')).not.toBeInTheDocument();
	});

	it('shows monogram fallback immediately when securityId is missing or null', () => {
		render(StockLogo, {
			props: {
				securityId: null,
				symbol: 'GOOGL'
			}
		});

		expect(screen.queryByRole('img')).not.toBeInTheDocument();
		const fallback = screen.getByTestId('stock-logo-fallback');
		expect(fallback).toBeInTheDocument();
		expect(fallback).toHaveTextContent('GO');
	});

	it('hides fallback once image is loaded', async () => {
		render(StockLogo, {
			props: {
				securityId: 'sec-123',
				symbol: 'MSFT'
			}
		});

		const img = screen.getByRole('img');
		expect(img).toHaveClass('invisible');
		expect(screen.getByTestId('stock-logo-fallback')).toBeInTheDocument();

		await fireEvent.load(img);

		expect(img).not.toHaveClass('invisible');
		expect(screen.queryByTestId('stock-logo-fallback')).not.toBeInTheDocument();
	});

	it('applies sizing props and custom classes', () => {
		const { container } = render(StockLogo, {
			props: {
				securityId: 'sec-123',
				symbol: 'AAPL',
				size: 'lg',
				class: 'custom-logo-class'
			}
		});

		const logoContainer = container.querySelector('[data-testid="stock-logo"]');
		expect(logoContainer).toHaveClass('size-8');
		expect(logoContainer).toHaveClass('custom-logo-class');
	});
});

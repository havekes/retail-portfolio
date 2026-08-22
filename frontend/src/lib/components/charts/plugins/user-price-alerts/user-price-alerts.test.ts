import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType } from 'lightweight-charts';
import type { CanvasRenderingTarget2D, BitmapCoordinatesRenderingScope } from 'fancy-canvas';

vi.hoisted(() => {
	if (typeof globalThis.Path2D === 'undefined') {
		/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
		(globalThis as any).Path2D = class Path2D {
			addPath() {}
		};
	}
});

import { UserAlertsState, type UserAlertInfo } from './state';
import { MouseHandlers, type MousePosition } from './mouse';
import { UserPriceAlerts } from './user-price-alerts';
import { UserAlertPricePaneView } from './pane-view';
import { PriceScalePaneRenderer } from './price-scale-pane-renderer';
import { PaneRenderer } from './pane-renderer';
import {
	centreLabelInlinePadding,
	removeButtonWidth,
	averageWidthPerCharacter,
	clockIconPaths,
	clockPlusIconPaths
} from './constants';
import type { IRendererData } from './irenderer-data';

function createMockChartAndSeries() {
	const mockChartElement = document.createElement('div');
	Object.defineProperty(mockChartElement, 'clientWidth', { value: 800, configurable: true });
	Object.defineProperty(mockChartElement, 'clientHeight', { value: 500, configurable: true });
	mockChartElement.getBoundingClientRect = () => ({
		left: 0,
		top: 0,
		right: 800,
		bottom: 500,
		width: 800,
		height: 500,
		x: 0,
		y: 0,
		toJSON: () => {}
	});

	const timeScale = {
		coordinateToTime: vi.fn(() => null),
		timeToCoordinate: vi.fn(() => null),
		height: vi.fn(() => 30),
		width: vi.fn(() => 750)
	};

	const priceScale = {
		width: vi.fn(() => 50),
		applyOptions: vi.fn()
	};

	const series = {
		coordinateToPrice: vi.fn((y: number) => {
			if (y < 0 || y > 500) return null;
			return 500 - y;
		}),
		priceToCoordinate: vi.fn((price: number) => {
			if (price < 0 || price > 500) return null;
			return 500 - price;
		}),
		priceScale: vi.fn(() => priceScale),
		priceFormatter: vi.fn(() => ({
			format: (p: number) => p.toFixed(2)
		}))
	} as unknown as ISeriesApi<SeriesType>;

	const chart = {
		chartElement: vi.fn(() => mockChartElement),
		timeScale: vi.fn(() => timeScale),
		applyOptions: vi.fn()
	} as unknown as IChartApi;

	return { chart, series, mockChartElement, timeScale, priceScale };
}

function createMockCanvasTarget() {
	const drawCalls: { type: string; args: unknown[] }[] = [];
	const context = {
		save: vi.fn(() => drawCalls.push({ type: 'save', args: [] })),
		restore: vi.fn(() => drawCalls.push({ type: 'restore', args: [] })),
		beginPath: vi.fn(() => drawCalls.push({ type: 'beginPath', args: [] })),
		moveTo: vi.fn((x: number, y: number) => drawCalls.push({ type: 'moveTo', args: [x, y] })),
		lineTo: vi.fn((x: number, y: number) => drawCalls.push({ type: 'lineTo', args: [x, y] })),
		arc: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'arc', args })),
		fill: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'fill', args })),
		stroke: vi.fn(() => drawCalls.push({ type: 'stroke', args: [] })),
		fillRect: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'fillRect', args })),
		roundRect: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'roundRect', args })),
		fillText: vi.fn((text: string, x: number, y: number) =>
			drawCalls.push({ type: 'fillText', args: [text, x, y] })
		),
		measureText: vi.fn((text: string) => ({ width: text.length * 6 })),
		setLineDash: vi.fn((dash: number[]) => drawCalls.push({ type: 'setLineDash', args: [dash] })),
		translate: vi.fn((x: number, y: number) => drawCalls.push({ type: 'translate', args: [x, y] })),
		scale: vi.fn((x: number, y: number) => drawCalls.push({ type: 'scale', args: [x, y] })),
		strokeStyle: '',
		fillStyle: '',
		lineWidth: 1,
		font: '',
		textAlign: 'start',
		textBaseline: 'alphabetic'
	} as unknown as CanvasRenderingContext2D;

	const scope: BitmapCoordinatesRenderingScope = {
		context,
		horizontalPixelRatio: 2,
		verticalPixelRatio: 2,
		mediaSize: {
			width: 800,
			height: 500
		} as unknown as BitmapCoordinatesRenderingScope['mediaSize'],
		bitmapSize: {
			width: 1600,
			height: 1000
		} as unknown as BitmapCoordinatesRenderingScope['bitmapSize']
	};

	const target: CanvasRenderingTarget2D = {
		useBitmapCoordinateSpace: vi.fn((callback: (s: BitmapCoordinatesRenderingScope) => void) => {
			callback(scope);
		})
	} as unknown as CanvasRenderingTarget2D;

	return { target, context, scope, drawCalls };
}

describe('User Price Alerts Plugin', () => {
	describe('UserAlertsState', () => {
		let state: UserAlertsState;

		beforeEach(() => {
			state = new UserAlertsState();
		});

		it('initializes with empty alerts array', () => {
			expect(state.alerts()).toEqual([]);
		});

		it('adds alert with generated ID, sorts descending by price, and notifies subscribers', () => {
			const alertAddedHandler = vi.fn();
			const alertsChangedHandler = vi.fn();
			state.alertAdded().subscribe(alertAddedHandler);
			state.alertsChanged().subscribe(alertsChangedHandler);

			const id1 = state.addAlert(100);
			expect(typeof id1).toBe('string');
			expect(id1.length).toBeGreaterThan(0);
			expect(alertAddedHandler).toHaveBeenCalledWith({ id: id1, price: 100 });
			expect(alertsChangedHandler).toHaveBeenCalledTimes(1);

			const id2 = state.addAlert(250);
			const id3 = state.addAlert(50);

			// Alerts must be sorted descending by price: [250, 100, 50]
			const alerts = state.alerts();
			expect(alerts).toHaveLength(3);
			expect(alerts[0]).toEqual({ id: id2, price: 250 });
			expect(alerts[1]).toEqual({ id: id1, price: 100 });
			expect(alerts[2]).toEqual({ id: id3, price: 50 });
		});

		it('removes alert by ID, fires delegates, and no-ops when ID does not exist', () => {
			const alertRemovedHandler = vi.fn();
			const alertsChangedHandler = vi.fn();
			state.alertRemoved().subscribe(alertRemovedHandler);
			state.alertsChanged().subscribe(alertsChangedHandler);

			const id1 = state.addAlert(100);
			const id2 = state.addAlert(200);
			alertsChangedHandler.mockClear();

			// Remove existing alert
			state.removeAlert(id1);
			expect(alertRemovedHandler).toHaveBeenCalledWith(id1);
			expect(alertsChangedHandler).toHaveBeenCalledTimes(1);
			expect(state.alerts()).toEqual([{ id: id2, price: 200 }]);

			// Remove non-existent alert (no-op)
			alertRemovedHandler.mockClear();
			alertsChangedHandler.mockClear();
			state.removeAlert('non-existent-id');
			expect(alertRemovedHandler).not.toHaveBeenCalled();
			expect(alertsChangedHandler).not.toHaveBeenCalled();
			expect(state.alerts()).toEqual([{ id: id2, price: 200 }]);
		});

		it('replaces all alerts with setAlerts, sorts descending by price, and notifies subscribers', () => {
			const alertsChangedHandler = vi.fn();
			state.alertsChanged().subscribe(alertsChangedHandler);

			const initialList: UserAlertInfo[] = [
				{ id: 'a1', price: 120 },
				{ id: 'a2', price: 300 },
				{ id: 'a3', price: 180 }
			];

			state.setAlerts(initialList);
			expect(alertsChangedHandler).toHaveBeenCalledTimes(1);

			const alerts = state.alerts();
			expect(alerts).toEqual([
				{ id: 'a2', price: 300 },
				{ id: 'a3', price: 180 },
				{ id: 'a1', price: 120 }
			]);
		});

		it('provides alertChanged delegate and cleans up all delegates and alerts on destroy', () => {
			const alertAddedHandler = vi.fn();
			const alertRemovedHandler = vi.fn();
			const alertChangedHandler = vi.fn();
			const alertsChangedHandler = vi.fn();

			state.alertAdded().subscribe(alertAddedHandler);
			state.alertRemoved().subscribe(alertRemovedHandler);
			state.alertChanged().subscribe(alertChangedHandler);
			state.alertsChanged().subscribe(alertsChangedHandler);

			state.addAlert(150);
			expect(state.alerts()).toHaveLength(1);

			state.destroy();

			expect(state.alerts()).toHaveLength(0);
			expect(state.alertAdded().hasListeners()).toBe(false);
			expect(state.alertRemoved().hasListeners()).toBe(false);
			expect(state.alertChanged().hasListeners()).toBe(false);
			expect(state.alertsChanged().hasListeners()).toBe(false);
		});

		/**
		 * DEFECT REGRESSION FIXED TEST:
		 *
		 * Previous defect:
		 * UserAlertsState generated hex string IDs (e.g., toString(16)).
		 * When security-chart.svelte:440 parsed the ID with `Number(idStr)`, hex letters [a-f] evaluated to NaN.
		 *
		 * ARCH-T05 fixed behavior:
		 * UserAlertsState generates decimal numeric string IDs, so Number(idStr) produces a valid number.
		 */
		it('generates decimal numeric string IDs that evaluate to valid finite numbers when parsed with Number()', () => {
			const alertRemovedHandler = vi.fn();
			state.alertRemoved().subscribe(alertRemovedHandler);

			// Add multiple alerts to verify generated decimal numeric string IDs
			const ids: string[] = [];
			for (let i = 0; i < 20; i++) {
				ids.push(state.addAlert(100 + i));
			}

			// Validate all generated IDs are pure numeric strings
			expect(ids.every((id) => /^\d+$/.test(id))).toBe(true);

			// Verify each ID parses to a valid finite positive integer Number
			expect(ids.every((id) => Number.isFinite(Number(id)) && !Number.isNaN(Number(id)))).toBe(
				true
			);

			// Verify removal fires alertRemoved with numeric string that Number() successfully parses
			const testId = ids[0];
			state.removeAlert(testId);
			expect(alertRemovedHandler).toHaveBeenCalledWith(testId);

			const receivedId = alertRemovedHandler.mock.calls[0][0];
			const parsedNumber = Number(receivedId);
			expect(Number.isNaN(parsedNumber)).toBe(false);
			expect(Number.isFinite(parsedNumber)).toBe(true);
			expect(parsedNumber).toBeGreaterThan(0);
		});
	});

	describe('MouseHandlers', () => {
		let mouse: MouseHandlers;
		let mockData: ReturnType<typeof createMockChartAndSeries>;

		beforeEach(() => {
			mouse = new MouseHandlers();
			mockData = createMockChartAndSeries();
			mouse.attached(mockData.chart, mockData.series);
		});

		it('attaches event listeners to chart container and computes plot area mouse position', () => {
			const moveHandler = vi.fn();
			mouse.mouseMoved().subscribe(moveHandler);

			// Container dimensions: width 800, height 500. priceScaleWidth = 50, timeScaleHeight = 30
			// clientX: 400, clientY: 200 -> x = 400, y = 200
			// xPositionRelativeToPriceScale = 800 - 50 - 400 = 350
			const event = new MouseEvent('mousemove', { clientX: 400, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(event);

			expect(moveHandler).toHaveBeenCalledWith({
				x: 400,
				y: 200,
				xPositionRelativeToPriceScale: 350,
				overPriceScale: false,
				overTimeScale: false
			});
		});

		it('detects mouse over price scale and time scale zones', () => {
			const moveHandler = vi.fn();
			mouse.mouseMoved().subscribe(moveHandler);

			// Mouse over price scale (x = 760 > 750) -> xPositionRelativeToPriceScale = 800 - 50 - 760 = -10 < 0
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 760, clientY: 200 })
			);
			expect(moveHandler).toHaveBeenLastCalledWith(
				expect.objectContaining({
					overPriceScale: true,
					overTimeScale: false
				})
			);

			// Mouse over time scale (y = 480 > 500 - 30 = 470)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 400, clientY: 480 })
			);
			expect(moveHandler).toHaveBeenLastCalledWith(
				expect.objectContaining({
					overPriceScale: false,
					overTimeScale: true
				})
			);
		});

		it('dispatches null on mouseleave and mouse position on click', () => {
			const moveHandler = vi.fn();
			const clickHandler = vi.fn();
			mouse.mouseMoved().subscribe(moveHandler);
			mouse.clicked().subscribe(clickHandler);

			mockData.mockChartElement.dispatchEvent(new MouseEvent('mouseleave'));
			expect(moveHandler).toHaveBeenCalledWith(null);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 300, clientY: 150 })
			);
			expect(clickHandler).toHaveBeenCalledWith(
				expect.objectContaining({
					x: 300,
					y: 150
				})
			);
		});

		it('cleans up DOM listeners and delegates on detached', () => {
			const moveHandler = vi.fn();
			mouse.mouseMoved().subscribe(moveHandler);

			mouse.detached();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 400, clientY: 200 })
			);
			// Handlers unsubscribed/destroyed, no new calls
			expect(moveHandler).not.toHaveBeenCalled();
		});

		it('returns null for mouse position when series or chart is unattached', () => {
			const unattachedMouse = new MouseHandlers();
			const pos = unattachedMouse._determineMousePosition(
				new MouseEvent('mousemove', { clientX: 100, clientY: 100 })
			);
			expect(pos).toBeNull();
		});
	});

	describe('UserPriceAlerts Calculation & Hover Geometry', () => {
		let alertsPlugin: UserPriceAlerts;
		let mockData: ReturnType<typeof createMockChartAndSeries>;

		beforeEach(() => {
			alertsPlugin = new UserPriceAlerts();
			mockData = createMockChartAndSeries();
			alertsPlugin.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: vi.fn(),
				horzScaleBehavior: {} as never
			});
			alertsPlugin.setSymbolName('AAPL');
		});

		it('returns null from _calculateRendererData when series is not attached', () => {
			const detachedPlugin = new UserPriceAlerts();
			const data = detachedPlugin._calculateRendererData([], null);
			expect(data).toBeNull();
		});

		it('calculates crosshair and button data when mouse is active in chart area', () => {
			const mousePos: MousePosition = {
				x: 400,
				y: 200,
				xPositionRelativeToPriceScale: 350,
				overPriceScale: false,
				overTimeScale: false
			};

			const data = alertsPlugin._calculateRendererData([], mousePos);
			expect(data).not.toBeNull();
			expect(data?.crosshair).toEqual({
				y: 200,
				text: '300.00' // coordinateToPrice(200) = 300.00
			});
			expect(data?.button).not.toBeNull();
			expect(data?.button?.hovering).toBe(false);
		});

		it('suppresses crosshair and button when mouse is over time scale', () => {
			const mousePos: MousePosition = {
				x: 400,
				y: 480,
				xPositionRelativeToPriceScale: 350,
				overPriceScale: false,
				overTimeScale: true
			};

			const data = alertsPlugin._calculateRendererData([], mousePos);
			expect(data?.crosshair).toBeNull();
			expect(data?.button).toBeNull();
		});

		it('detects closest alert within 50px vertical distance and formats hover label', () => {
			// Alert at price 300 -> y = 200
			const alertInfo: UserAlertInfo = { id: 'alert-1', price: 300 };

			// Mouse at y = 220 (distance = 20px <= 50px)
			const mousePos: MousePosition = {
				x: 400,
				y: 220,
				xPositionRelativeToPriceScale: 350,
				overPriceScale: false,
				overTimeScale: false
			};

			const data = alertsPlugin._calculateRendererData([alertInfo], mousePos);
			expect(data?.alerts).toHaveLength(1);
			const alert = data?.alerts[0];
			expect(alert?.showHover).toBe(true);
			if (alert?.showHover) {
				expect(alert.text).toBe('AAPL crossing 300.00');
				expect(alert.hoverRemove).toBe(false);
			}
		});

		it('sets showHover to false when mouse is outside the 50px distance threshold', () => {
			// Alert at price 300 -> y = 200
			const alertInfo: UserAlertInfo = { id: 'alert-1', price: 300 };

			// Mouse at y = 280 (distance = 80px > 50px)
			const mousePos: MousePosition = {
				x: 400,
				y: 280,
				xPositionRelativeToPriceScale: 350,
				overPriceScale: false,
				overTimeScale: false
			};

			const data = alertsPlugin._calculateRendererData([alertInfo], mousePos);
			expect(data?.alerts[0].showHover).toBe(false);
		});

		it('evaluates price scale add-button hover geometry (_isHovering)', () => {
			// buttonWidth is 21; hover requires 1 <= xPositionRelativeToPriceScale < 21
			expect(
				alertsPlugin._isHovering({
					x: 740,
					y: 200,
					xPositionRelativeToPriceScale: 10,
					overPriceScale: false,
					overTimeScale: false
				})
			).toBe(true);

			expect(
				alertsPlugin._isHovering({
					x: 740,
					y: 200,
					xPositionRelativeToPriceScale: 0.5, // < 1
					overPriceScale: false,
					overTimeScale: false
				})
			).toBe(false);

			expect(
				alertsPlugin._isHovering({
					x: 740,
					y: 200,
					xPositionRelativeToPriceScale: 25, // >= 21
					overPriceScale: false,
					overTimeScale: false
				})
			).toBe(false);

			expect(alertsPlugin._isHovering(null)).toBe(false);
		});

		it('evaluates remove-button hover geometry (_isHoveringRemoveButton)', () => {
			const timescaleWidth = 750;
			const alertY = 200;
			const textLength = 'AAPL crossing 300.00'.length; // 20 chars

			// centreLabelHeight = 20 (Y radius = 10)
			// labelWidth = 9*2 + 26 + 20*5.81 = 18 + 26 + 116.2 = 160.2
			// buttonCentreX = (750 + 160.2 - 26) * 0.5 = 442.1
			// removeButtonWidth = 26 (X radius = 13)
			const labelWidth =
				centreLabelInlinePadding * 2 + removeButtonWidth + textLength * averageWidthPerCharacter;
			const buttonCentreX = (timescaleWidth + labelWidth - removeButtonWidth) * 0.5;

			// Inside remove button bounds
			const insideMouse: MousePosition = {
				x: buttonCentreX,
				y: alertY,
				xPositionRelativeToPriceScale: 300,
				overPriceScale: false,
				overTimeScale: false
			};
			expect(
				alertsPlugin._isHoveringRemoveButton(insideMouse, timescaleWidth, alertY, textLength)
			).toBe(true);

			// Outside Y bounds (> 10px from alertY)
			const outsideYMouse: MousePosition = {
				...insideMouse,
				y: alertY + 15
			};
			expect(
				alertsPlugin._isHoveringRemoveButton(outsideYMouse, timescaleWidth, alertY, textLength)
			).toBe(false);

			// Outside X bounds (> 13px from buttonCentreX)
			const outsideXMouse: MousePosition = {
				...insideMouse,
				x: buttonCentreX + 20
			};
			expect(
				alertsPlugin._isHoveringRemoveButton(outsideXMouse, timescaleWidth, alertY, textLength)
			).toBe(false);

			// Null mouse or 0 timescale width
			expect(alertsPlugin._isHoveringRemoveButton(null, timescaleWidth, alertY, textLength)).toBe(
				false
			);
			expect(alertsPlugin._isHoveringRemoveButton(insideMouse, 0, alertY, textLength)).toBe(false);
		});

		it('updates cursor style to pointer when hovering add button or remove button', () => {
			alertsPlugin.setAlerts([{ id: 'a1', price: 300 }]);

			// 1. Initial state: not hovering -> hitTest is null
			alertsPlugin.updateAllViews();
			expect(alertsPlugin.hitTest()).toBeNull();

			// 2. Hovering add button
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 740, clientY: 200 })
			);
			alertsPlugin.updateAllViews();
			expect(alertsPlugin.hitTest()).toEqual({
				cursorStyle: 'pointer',
				externalId: 'user-alerts-primitive',
				zOrder: 'top'
			});
		});

		it('does not mutate _hoveringID or instance fields during _calculateRendererData', () => {
			const alertInfo: UserAlertInfo = { id: 'alert-123', price: 300 };
			const timescaleWidth = 750;
			const textLength = 'AAPL crossing 300.00'.length;
			const labelWidth =
				centreLabelInlinePadding * 2 + removeButtonWidth + textLength * averageWidthPerCharacter;
			const buttonCentreX = (timescaleWidth + labelWidth - removeButtonWidth) * 0.5;

			const mousePos: MousePosition = {
				x: buttonCentreX,
				y: 200,
				xPositionRelativeToPriceScale: 300,
				overPriceScale: false,
				overTimeScale: false
			};

			// Initial state
			// @ts-expect-error accessing private field for side-effect assertion
			expect(alertsPlugin._hoveringID).toBe('');

			// Calling _calculateRendererData directly calculates hover data without mutating _hoveringID
			const data = alertsPlugin._calculateRendererData([alertInfo], mousePos);
			expect(data?.alerts[0].showHover).toBe(true);
			if (data?.alerts[0].showHover) {
				expect(data.alerts[0].hoverRemove).toBe(true);
			}

			// @ts-expect-error accessing private field for side-effect assertion
			expect(alertsPlugin._hoveringID).toBe('');

			// _hoveringID is updated only when updateAllViews() is called
			alertsPlugin.setAlerts([alertInfo]);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: Math.round(buttonCentreX), clientY: 200 })
			);
			alertsPlugin.updateAllViews();
			// @ts-expect-error accessing private field for side-effect assertion
			expect(alertsPlugin._hoveringID).toBe('alert-123');
		});
	});

	describe('UserPriceAlerts Interaction and Lifecycle', () => {
		let alertsPlugin: UserPriceAlerts;
		let mockData: ReturnType<typeof createMockChartAndSeries>;
		let requestUpdate: ReturnType<typeof vi.fn>;

		beforeEach(() => {
			alertsPlugin = new UserPriceAlerts();
			mockData = createMockChartAndSeries();
			requestUpdate = vi.fn();
			alertsPlugin.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: requestUpdate as () => void,
				horzScaleBehavior: {} as never
			});
		});

		it('provides paneViews and priceAxisPaneViews', () => {
			expect(alertsPlugin.paneViews()).toHaveLength(1);
			expect(alertsPlugin.priceAxisPaneViews()).toHaveLength(1);
		});

		it('adds alert on click when hovering price scale button zone', () => {
			const alertAddedHandler = vi.fn();
			alertsPlugin.alertAdded().subscribe(alertAddedHandler);

			// clientX 740 is within buttonWidth from price scale (800 - 50 - 740 = 10)
			// clientY 200 converts to price 300 (500 - 200 = 300)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 740, clientY: 200 })
			);

			expect(alertAddedHandler).toHaveBeenCalledWith(
				expect.objectContaining({
					price: 300
				})
			);
			expect(requestUpdate).toHaveBeenCalled();
		});

		it('removes alert on click when hovering alert remove button', () => {
			const id = alertsPlugin.addAlert(300); // y = 200
			alertsPlugin.setSymbolName('AAPL');
			requestUpdate.mockClear();

			const textLength = 'AAPL crossing 300.00'.length;
			const labelWidth =
				centreLabelInlinePadding * 2 + removeButtonWidth + textLength * averageWidthPerCharacter;
			const buttonCentreX = (750 + labelWidth - removeButtonWidth) * 0.5;

			// Move mouse over remove button to trigger hoverRemove and record _hoveringID
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: Math.round(buttonCentreX), clientY: 200 })
			);
			alertsPlugin.updateAllViews();

			const alertRemovedHandler = vi.fn();
			alertsPlugin.alertRemoved().subscribe(alertRemovedHandler);

			// Click on remove button
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: Math.round(buttonCentreX), clientY: 200 })
			);

			expect(alertRemovedHandler).toHaveBeenCalledWith(id);
			expect(requestUpdate).toHaveBeenCalled();
		});

		it('cleans up delegates and mouse handlers on detached', () => {
			alertsPlugin.detached();
			requestUpdate.mockClear();

			// Subsequent mouse moves or clicks should not fire updates
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 400, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 740, clientY: 200 })
			);

			expect(requestUpdate).not.toHaveBeenCalled();
		});

		it('delegates alerts state methods via composition', () => {
			expect(alertsPlugin.alerts()).toEqual([]);

			const id = alertsPlugin.addAlert(200);
			expect(typeof id).toBe('string');
			expect(alertsPlugin.alerts()).toEqual([{ id, price: 200 }]);

			alertsPlugin.setAlerts([{ id: '999', price: 400 }]);
			expect(alertsPlugin.alerts()).toEqual([{ id: '999', price: 400 }]);

			alertsPlugin.removeAlert('999');
			expect(alertsPlugin.alerts()).toEqual([]);
		});

		it('cleans up detached listeners and destroys internal state on destroy()', () => {
			const alertAddedHandler = vi.fn();
			alertsPlugin.alertAdded().subscribe(alertAddedHandler);

			alertsPlugin.destroy();

			expect(alertsPlugin.alertAdded().hasListeners()).toBe(false);
			expect(alertsPlugin.alertRemoved().hasListeners()).toBe(false);
			expect(alertsPlugin.alertChanged().hasListeners()).toBe(false);
			expect(alertsPlugin.alertsChanged().hasListeners()).toBe(false);
			expect(alertsPlugin.alerts()).toEqual([]);
		});
	});

	describe('Renderers: UserAlertPricePaneView, PriceScalePaneRenderer, PaneRenderer', () => {
		let mockCanvas: ReturnType<typeof createMockCanvasTarget>;

		beforeEach(() => {
			mockCanvas = createMockCanvasTarget();
		});

		it('UserAlertPricePaneView instantiates proper renderer and returns zOrder top', () => {
			const paneView = new UserAlertPricePaneView(false);
			expect(paneView.zOrder()).toBe('top');
			expect(paneView.renderer()).toBeInstanceOf(PaneRenderer);

			const pricePaneView = new UserAlertPricePaneView(true);
			expect(pricePaneView.zOrder()).toBe('top');
			expect(pricePaneView.renderer()).toBeInstanceOf(PriceScalePaneRenderer);
		});

		it('PriceScalePaneRenderer draws crosshair background box and right-aligned text', () => {
			const renderer = new PriceScalePaneRenderer();
			const renderData: IRendererData = {
				color: '#131722',
				alertIcon: clockIconPaths,
				alerts: [],
				button: null,
				crosshair: {
					y: 200,
					text: '300.00'
				}
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.target.useBitmapCoordinateSpace).toHaveBeenCalled();

			const roundRectCalls = mockCanvas.drawCalls.filter((c) => c.type === 'roundRect');
			expect(roundRectCalls.length).toBeGreaterThanOrEqual(1);

			const fillTextCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(fillTextCalls).toHaveLength(1);
			expect(fillTextCalls[0].args[0]).toBe('300.00');
		});

		it('PriceScalePaneRenderer no-ops on null data or null crosshair', () => {
			const renderer = new PriceScalePaneRenderer();
			renderer.update(null);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls).toHaveLength(0);

			renderer.update({
				color: '#131722',
				alertIcon: clockIconPaths,
				alerts: [],
				button: null,
				crosshair: null
			});
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls).toHaveLength(0);
		});

		it('PaneRenderer draws dashed lines, clock icons, crosshair line and add button', () => {
			const renderer = new PaneRenderer();
			const renderData: IRendererData = {
				color: '#131722',
				alertIcon: clockIconPaths,
				alerts: [
					{
						y: 200,
						showHover: false
					}
				],
				button: {
					hovering: false,
					hoverColor: '#50535E',
					crosshairLabelIcon: clockPlusIconPaths
				},
				crosshair: {
					y: 150,
					text: '350.00'
				}
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			const setLineDashCalls = mockCanvas.drawCalls.filter((c) => c.type === 'setLineDash');
			expect(setLineDashCalls.length).toBeGreaterThanOrEqual(2); // Alert line + Crosshair line

			const fillCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fill');
			expect(fillCalls.length).toBeGreaterThanOrEqual(2); // Alert icon + Crosshair add button
		});

		it('PaneRenderer suppresses crosshair line and button when remove button is hovered', () => {
			const renderer = new PaneRenderer();
			const renderData: IRendererData = {
				color: '#131722',
				alertIcon: clockIconPaths,
				alerts: [
					{
						y: 200,
						showHover: true,
						hoverRemove: true,
						text: 'AAPL crossing 300.00'
					}
				],
				button: {
					hovering: false,
					hoverColor: '#50535E',
					crosshairLabelIcon: clockPlusIconPaths
				},
				crosshair: {
					y: 150,
					text: '350.00'
				}
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			// Alert dashed line is drawn, but crosshair dashed line is omitted
			const setLineDashCalls = mockCanvas.drawCalls.filter((c) => c.type === 'setLineDash');
			expect(setLineDashCalls).toHaveLength(1);

			// Centered alert hover badge with text is drawn
			const fillTextCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(fillTextCalls).toHaveLength(1);
			expect(fillTextCalls[0].args[0]).toBe('AAPL crossing 300.00');

			// Remove button background divider is drawn
			const fillRectCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fillRect');
			expect(fillRectCalls).toHaveLength(1);
		});

		it('PaneRenderer no-ops on null data', () => {
			const renderer = new PaneRenderer();
			renderer.update(null);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls).toHaveLength(0);
		});
	});
});

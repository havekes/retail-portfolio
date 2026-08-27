import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import RewindTimeline from './rewind-timeline.svelte';
import {
	snapshotTimelineDomain,
	timeToFraction,
	fractionToTime,
	sliceCandlesBefore
} from './rewind-timeline';
import type { UTCTimestamp } from 'lightweight-charts';
import type { RewindSnapshot } from '$lib/utils/finance/rewind';
import type { Candle } from '@/utils/finance/candle';

describe('rewind-timeline pure helpers', () => {
	const sampleSnapshots: RewindSnapshot[] = [
		{
			id: 'snap-1',
			captured_at: '2024-01-01T00:00:00.000Z',
			drawings: {},
			data_window: { first: '2024-01-01', last: '2024-01-02' }
		},
		{
			id: 'snap-2',
			captured_at: '2024-01-02T00:00:00.000Z',
			drawings: {},
			data_window: { first: '2024-01-01', last: '2024-01-03' }
		}
	];

	describe('snapshotTimelineDomain', () => {
		it('derives first from oldest snapshot captured_at and last from now', () => {
			const now = new Date('2024-01-03T00:00:00.000Z');
			const domain = snapshotTimelineDomain(sampleSnapshots, now);

			expect(domain.first).toBe(Date.parse('2024-01-01T00:00:00.000Z'));
			expect(domain.last).toBe(now.getTime());
			expect(domain.last).toBeGreaterThan(domain.first);
		});

		it('guards against last <= first when now is earlier than or equal to first snapshot', () => {
			const now = new Date('2023-12-31T00:00:00.000Z');
			const domain = snapshotTimelineDomain(sampleSnapshots, now);

			const expectedFirst = Date.parse('2024-01-01T00:00:00.000Z');
			expect(domain.first).toBe(expectedFirst);
			expect(domain.last).toBe(expectedFirst + 1);
		});

		it('guards against last === first when now is exactly equal to first snapshot', () => {
			const now = new Date('2024-01-01T00:00:00.000Z');
			const domain = snapshotTimelineDomain(sampleSnapshots, now);

			const expectedFirst = Date.parse('2024-01-01T00:00:00.000Z');
			expect(domain.first).toBe(expectedFirst);
			expect(domain.last).toBe(expectedFirst + 1);
		});

		it('handles empty snapshots list gracefully', () => {
			const now = new Date('2024-01-01T12:00:00.000Z');
			const domain = snapshotTimelineDomain([], now);

			expect(domain.first).toBe(now.getTime());
			expect(domain.last).toBe(now.getTime() + 1);
		});
	});

	describe('timeToFraction', () => {
		const first = 10000;
		const last = 20000;

		it('returns 0 for first, 0.5 for midpoint, and 1 for last', () => {
			expect(timeToFraction(first, first, last)).toBe(0);
			expect(timeToFraction(15000, first, last)).toBe(0.5);
			expect(timeToFraction(last, first, last)).toBe(1);
		});

		it('accepts Date instances', () => {
			expect(timeToFraction(new Date(15000), first, last)).toBe(0.5);
		});

		it('clamps out-of-range timestamps to [0, 1]', () => {
			expect(timeToFraction(5000, first, last)).toBe(0);
			expect(timeToFraction(25000, first, last)).toBe(1);
		});

		it('returns 0 when last <= first to avoid division by zero', () => {
			expect(timeToFraction(10000, 10000, 10000)).toBe(0);
			expect(timeToFraction(10000, 10000, 9000)).toBe(0);
		});
	});

	describe('fractionToTime', () => {
		const first = 10000;
		const last = 20000;

		it('maps 0 to first and 1 to last', () => {
			expect(fractionToTime(0, first, last).getTime()).toBe(first);
			expect(fractionToTime(1, first, last).getTime()).toBe(last);
		});

		it('maps 0.5 to midpoint', () => {
			expect(fractionToTime(0.5, first, last).getTime()).toBe(15000);
		});

		it('acts as the inverse of timeToFraction', () => {
			const f = 0.35;
			const time = fractionToTime(f, first, last);
			const reconstructedFraction = timeToFraction(time.getTime(), first, last);
			expect(reconstructedFraction).toBeCloseTo(f, 5);
		});

		it('clamps fractions < 0 and > 1', () => {
			expect(fractionToTime(-0.5, first, last).getTime()).toBe(first);
			expect(fractionToTime(1.5, first, last).getTime()).toBe(last);
		});
	});

	describe('sliceCandlesBefore', () => {
		const dailyCandles: Candle[] = [
			{ time: '2024-01-01', open: 10, high: 12, low: 9, close: 11, volume: 100 },
			{ time: '2024-01-02', open: 11, high: 13, low: 10, close: 12, volume: 110 },
			{ time: '2024-01-03', open: 12, high: 14, low: 11, close: 13, volume: 120 }
		];

		const intradayCandles: Candle[] = [
			{ time: 1704067200 as UTCTimestamp, open: 10, high: 12, low: 9, close: 11, volume: 100 }, // 2024-01-01T00:00:00Z
			{ time: 1704153600 as UTCTimestamp, open: 11, high: 13, low: 10, close: 12, volume: 110 }, // 2024-01-02T00:00:00Z
			{ time: 1704240000 as UTCTimestamp, open: 12, high: 14, low: 11, close: 13, volume: 120 } // 2024-01-03T00:00:00Z
		];

		it('returns all candles when cutoff is null', () => {
			const result = sliceCandlesBefore(dailyCandles, null);
			expect(result).toEqual(dailyCandles);
		});

		it('returns all candles when cutoff is invalid date', () => {
			const result = sliceCandlesBefore(dailyCandles, new Date('invalid'));
			expect(result).toEqual(dailyCandles);
		});

		it('slices daily date string candles up to cutoff', () => {
			const cutoff = new Date('2024-01-02T12:00:00.000Z');
			const result = sliceCandlesBefore(dailyCandles, cutoff);
			expect(result).toHaveLength(2);
			expect(result[0].time).toBe('2024-01-01');
			expect(result[1].time).toBe('2024-01-02');
		});

		it('slices intraday timestamp candles up to cutoff', () => {
			const cutoff = new Date(1704153600 * 1000); // exactly second candle
			const result = sliceCandlesBefore(intradayCandles, cutoff);
			expect(result).toHaveLength(2);
			expect(result[0].time).toBe(1704067200);
			expect(result[1].time).toBe(1704153600);
		});

		it('returns empty array when cutoff is before first candle', () => {
			const cutoff = new Date('2023-12-31T23:59:59.999Z');
			const result = sliceCandlesBefore(dailyCandles, cutoff);
			expect(result).toHaveLength(0);
		});

		it('returns all candles when cutoff is after last candle', () => {
			const cutoff = new Date('2024-01-04T00:00:00.000Z');
			const result = sliceCandlesBefore(dailyCandles, cutoff);
			expect(result).toHaveLength(3);
			expect(result).toEqual(dailyCandles);
		});
	});
});

describe('RewindTimeline Component', () => {
	it('renders defined empty state when snapshots list is empty', () => {
		render(RewindTimeline, {
			props: {
				snapshots: [],
				now: new Date('2024-01-03T00:00:00.000Z')
			}
		});

		const strip = screen.getByTestId('rewind-timeline');
		expect(strip).toBeInTheDocument();
		expect(screen.getByText('No rewind snapshots yet')).toBeInTheDocument();
		expect(screen.queryByTestId('rewind-snapshot-point')).not.toBeInTheDocument();
		expect(screen.queryByTestId('rewind-playhead')).not.toBeInTheDocument();
	});

	it('renders snapshot points at correct relative left positions and default playhead at right end', () => {
		const snapshots: RewindSnapshot[] = [
			{
				id: 'snap-1',
				captured_at: '2024-01-01T00:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-02' }
			},
			{
				id: 'snap-2',
				captured_at: '2024-01-02T00:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-03' }
			},
			{
				id: 'snap-3',
				captured_at: '2024-01-02T12:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-03' }
			}
		];
		// Total span: from 2024-01-01T00:00:00 to 2024-01-03T00:00:00 = 48 hours
		// snap-1: 0 hours -> 0%
		// snap-2: 24 hours -> 50%
		// snap-3: 36 hours -> 75%
		const now = new Date('2024-01-03T00:00:00.000Z');

		render(RewindTimeline, {
			props: {
				snapshots,
				now
			}
		});

		const points = screen.getAllByTestId('rewind-snapshot-point');
		expect(points).toHaveLength(3);

		expect(points[0].style.left).toBe('0%');
		expect(points[1].style.left).toBe('50%');
		expect(points[2].style.left).toBe('75%');

		// Highlighted zone
		const zone = screen.getByTestId('rewind-timeline-zone');
		expect(zone).toBeInTheDocument();

		// Playhead defaults to "now" (right end: 100%)
		const playhead = screen.getByTestId('rewind-playhead');
		expect(playhead).toBeInTheDocument();
		expect(playhead.style.left).toBe('100%');

		// Start and Now labels
		expect(screen.getByTestId('rewind-start-label')).toBeInTheDocument();
		expect(screen.getByText('Now')).toBeInTheDocument();
	});

	it('positions playhead at specific position date when passed', () => {
		const snapshots: RewindSnapshot[] = [
			{
				id: 'snap-1',
				captured_at: '2024-01-01T00:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-02' }
			}
		];
		const now = new Date('2024-01-03T00:00:00.000Z');
		// position at 2024-01-02T00:00:00 is exactly 50%
		const customPosition = new Date('2024-01-02T00:00:00.000Z');

		render(RewindTimeline, {
			props: {
				snapshots,
				now,
				position: customPosition
			}
		});

		const playhead = screen.getByTestId('rewind-playhead');
		expect(playhead.style.left).toBe('50%');
	});

	it('scrubbing via pointerdown updates position and calls onScrub', async () => {
		const onScrub = vi.fn();
		const snapshots: RewindSnapshot[] = [
			{
				id: 'snap-1',
				captured_at: '2024-01-01T00:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-02' }
			}
		];
		const now = new Date('2024-01-03T00:00:00.000Z');

		render(RewindTimeline, {
			props: {
				snapshots,
				now,
				onScrub
			}
		});

		const zone = screen.getByTestId('rewind-timeline-zone');
		vi.spyOn(zone, 'getBoundingClientRect').mockReturnValue({
			left: 0,
			top: 0,
			width: 100,
			height: 20,
			right: 100,
			bottom: 20,
			x: 0,
			y: 0,
			toJSON: () => {}
		});

		// 50% fraction -> 2024-01-02T00:00:00.000Z
		await fireEvent.pointerDown(zone, { clientX: 50, pointerId: 1 });
		expect(onScrub).toHaveBeenCalledTimes(1);
		const scrubbedDate = onScrub.mock.calls[0][0] as Date;
		expect(scrubbedDate.toISOString()).toBe('2024-01-02T00:00:00.000Z');

		// pointermove to 25% fraction -> 2024-01-01T12:00:00.000Z
		await fireEvent.pointerMove(zone, { clientX: 25, pointerId: 1 });
		expect(onScrub).toHaveBeenCalledTimes(2);
		const movedDate = onScrub.mock.calls[1][0] as Date;
		expect(movedDate.toISOString()).toBe('2024-01-01T12:00:00.000Z');

		// pointermove to >= 99.5% snaps to null (now)
		await fireEvent.pointerMove(zone, { clientX: 100, pointerId: 1 });
		expect(onScrub).toHaveBeenCalledTimes(3);
		expect(onScrub.mock.calls[2][0]).toBeNull();

		await fireEvent.pointerUp(zone, { clientX: 100, pointerId: 1 });
	});

	it('clicking snapshot marker sets position directly to captured_at and calls onScrub', async () => {
		const onScrub = vi.fn();
		const snapshots: RewindSnapshot[] = [
			{
				id: 'snap-1',
				captured_at: '2024-01-01T06:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-02' }
			}
		];
		const now = new Date('2024-01-03T00:00:00.000Z');

		render(RewindTimeline, {
			props: {
				snapshots,
				now,
				onScrub
			}
		});

		const marker = screen.getByTestId('rewind-snapshot-point');
		await fireEvent.click(marker);

		expect(onScrub).toHaveBeenCalledTimes(1);
		const scrubbedDate = onScrub.mock.calls[0][0] as Date;
		expect(scrubbedDate.toISOString()).toBe('2024-01-01T06:00:00.000Z');
	});

	it('clicking "Now" button restores position to null and calls onScrub(null)', async () => {
		const onScrub = vi.fn();
		const snapshots: RewindSnapshot[] = [
			{
				id: 'snap-1',
				captured_at: '2024-01-01T00:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-02' }
			}
		];
		const now = new Date('2024-01-03T00:00:00.000Z');
		const customPosition = new Date('2024-01-02T00:00:00.000Z');

		render(RewindTimeline, {
			props: {
				snapshots,
				now,
				position: customPosition,
				onScrub
			}
		});

		const nowBtn = screen.getByTestId('rewind-end-label');
		await fireEvent.click(nowBtn);

		expect(onScrub).toHaveBeenCalledWith(null);
	});

	it('clicking "Back to now" button restores position to null and hides the button', async () => {
		const onScrub = vi.fn();
		const snapshots: RewindSnapshot[] = [
			{
				id: 'snap-1',
				captured_at: '2024-01-01T00:00:00.000Z',
				drawings: {},
				data_window: { first: '2024-01-01', last: '2024-01-02' }
			}
		];
		const now = new Date('2024-01-03T00:00:00.000Z');
		const customPosition = new Date('2024-01-02T00:00:00.000Z');

		const { rerender } = render(RewindTimeline, {
			props: {
				snapshots,
				now,
				position: customPosition,
				onScrub
			}
		});

		const backToNowBtn = screen.getByTestId('rewind-back-to-now');
		expect(backToNowBtn).toBeInTheDocument();
		expect(backToNowBtn).toHaveTextContent('Back to now');

		await fireEvent.click(backToNowBtn);
		expect(onScrub).toHaveBeenCalledWith(null);

		// If position becomes null, Back to now button disappears
		rerender({ snapshots, now, position: null });
		expect(screen.queryByTestId('rewind-back-to-now')).not.toBeInTheDocument();
	});
});

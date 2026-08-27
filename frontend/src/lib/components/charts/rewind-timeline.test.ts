import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import RewindTimeline from './rewind-timeline.svelte';
import { snapshotTimelineDomain, timeToFraction, fractionToTime } from './rewind-timeline';
import type { RewindSnapshot } from '$lib/utils/finance/rewind';

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
});

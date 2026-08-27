import type { SecurityElliottWaves } from './elliott-wave';
import type { SecurityFibonacciTools } from './fibonacci';
import { areWaveCountsEqual } from './elliott-wave';
import { areFibonacciToolsEqual } from './fibonacci';

export interface RewindDataWindow {
	first: string | number; // getTimeValue()-stringified candle time
	last: string | number;
}

export interface RewindDrawings {
	elliott_waves?: SecurityElliottWaves | null;
	fibonacci_tools?: SecurityFibonacciTools | null;
}

export interface RewindSnapshot {
	id: string; // unique
	captured_at: string; // ISO-8601 UTC (Date#toISOString())
	drawings: RewindDrawings;
	data_window: RewindDataWindow;
}

/**
 * Captures a new rewind snapshot with a unique ID and ISO-8601 UTC timestamp.
 */
export function captureSnapshot(
	drawings: RewindDrawings,
	dataWindow: RewindDataWindow,
	now: Date = new Date()
): RewindSnapshot {
	return {
		id: crypto.randomUUID(),
		captured_at: now.toISOString(),
		drawings,
		data_window: dataWindow
	};
}

/**
 * Immutably appends a snapshot to a security's snapshot list, returning a new map.
 * Never mutates inputs; handles null/undefined/missing key gracefully.
 */
export function appendSnapshot(
	allSnapshots: Record<string, RewindSnapshot[]> | null | undefined,
	securityId: string,
	snapshot: RewindSnapshot
): Record<string, RewindSnapshot[]> {
	const currentList = allSnapshots?.[securityId] ?? [];
	return {
		...(allSnapshots ?? {}),
		[securityId]: [...currentList, snapshot]
	};
}

/**
 * Returns a new array of the per-security snapshot list sorted ascending by captured_at
 * (oldest to newest). ISO-UTC strings compare lexicographically / chronologically.
 * Returns an empty array when absent or empty; never mutates input.
 */
export function getSnapshots(
	allSnapshots: Record<string, RewindSnapshot[]> | null | undefined,
	securityId: string
): RewindSnapshot[] {
	if (!allSnapshots || !securityId) {
		return [];
	}
	const list = allSnapshots[securityId];
	if (!list || list.length === 0) {
		return [];
	}
	return [...list].sort((a, b) =>
		a.captured_at < b.captured_at ? -1 : a.captured_at > b.captured_at ? 1 : 0
	);
}

/**
 * Returns the latest snapshot captured at or before the given wall-clock time.
 * Returns null when none qualify (i.e. time is before the first snapshot) or when the list is missing/empty.
 * When time is after the last snapshot, returns the last snapshot.
 */
export function findSnapshotAtOrBefore(
	allSnapshots: Record<string, RewindSnapshot[]> | null | undefined,
	securityId: string,
	time: Date
): RewindSnapshot | null {
	const snapshots = getSnapshots(allSnapshots, securityId);
	if (snapshots.length === 0) {
		return null;
	}

	const targetTime = time.getTime();
	if (isNaN(targetTime)) {
		return null;
	}

	for (let i = snapshots.length - 1; i >= 0; i--) {
		const snapTime = Date.parse(snapshots[i].captured_at);
		if (snapTime <= targetTime) {
			return snapshots[i];
		}
	}

	return null;
}

function areDataWindowsEqual(
	a: RewindDataWindow | null | undefined,
	b: RewindDataWindow | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	return String(a.first) === String(b.first) && String(a.last) === String(b.last);
}

function areSecurityElliottWavesEqual(
	a: SecurityElliottWaves | null | undefined,
	b: SecurityElliottWaves | null | undefined
): boolean {
	if (!a && !b) return true;
	return (
		areWaveCountsEqual(a?.cycle, b?.cycle) &&
		areWaveCountsEqual(a?.primary, b?.primary) &&
		areWaveCountsEqual(a?.intermediate, b?.intermediate)
	);
}

function areFibonacciToolsEqualNormalized(
	a: SecurityFibonacciTools | null | undefined,
	b: SecurityFibonacciTools | null | undefined
): boolean {
	const aEmpty = !a || (!a.retracement && !a.extension);
	const bEmpty = !b || (!b.retracement && !b.extension);
	if (aEmpty && bEmpty) return true;
	return areFibonacciToolsEqual(a, b);
}

/**
 * Compares two RewindSnapshot objects for content equality (structural equality of drawings
 * and data window). Metadata fields `id` and `captured_at` are intentionally ignored for save-dedupe semantics.
 */
export function areSnapshotsEqual(
	a: RewindSnapshot | null | undefined,
	b: RewindSnapshot | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;

	if (!areDataWindowsEqual(a.data_window, b.data_window)) {
		return false;
	}

	if (!areSecurityElliottWavesEqual(a.drawings?.elliott_waves, b.drawings?.elliott_waves)) {
		return false;
	}

	if (!areFibonacciToolsEqualNormalized(a.drawings?.fibonacci_tools, b.drawings?.fibonacci_tools)) {
		return false;
	}

	return true;
}

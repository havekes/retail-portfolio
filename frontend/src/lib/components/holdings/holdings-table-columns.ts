/**
 * Pure configuration for the spreadsheet-style holdings table.
 *
 * Holds the canonical column order/labels, default widths, the bounds a drag may
 * move a column within, and the normalize/merge fallback used when loading the
 * persisted `holdings_table` preference. Deliberately free of DOM/Svelte imports
 * so it can be unit-tested standalone and imported from API/preference modules.
 */

export const HOLDINGS_TABLE_COLUMN_IDS = [
	'security_symbol',
	'account_name',
	'quantity',
	'average_cost',
	'latest_price',
	'total_value',
	'profit_loss',
	'profit_loss_percent'
] as const;

export type HoldingsTableColumnId = (typeof HOLDINGS_TABLE_COLUMN_IDS)[number];

export type HoldingsTableColumn = {
	id: HoldingsTableColumnId;
	label: string;
	alignRight: boolean;
};

export const HOLDINGS_TABLE_COLUMNS: readonly HoldingsTableColumn[] = [
	{ id: 'security_symbol', label: 'Security', alignRight: false },
	{ id: 'account_name', label: 'Account', alignRight: false },
	{ id: 'quantity', label: 'Quantity', alignRight: true },
	{ id: 'average_cost', label: 'Avg Cost', alignRight: true },
	{ id: 'latest_price', label: 'Price', alignRight: true },
	{ id: 'total_value', label: 'Total Value', alignRight: true },
	{ id: 'profit_loss', label: 'Profit/Loss', alignRight: true },
	{ id: 'profit_loss_percent', label: 'P/L %', alignRight: true }
];

/**
 * The first column is the sticky row header. Hiding it collapses the sticky
 * layout, so it can never be hidden (the visibility menu disables it).
 */
export const HOLDINGS_TABLE_STICKY_COLUMN_ID: HoldingsTableColumnId = 'security_symbol';

export const HOLDINGS_TABLE_DEFAULT_WIDTHS: Record<HoldingsTableColumnId, number> = {
	security_symbol: 220,
	account_name: 140,
	quantity: 110,
	average_cost: 150,
	latest_price: 150,
	total_value: 170,
	profit_loss: 160,
	profit_loss_percent: 110
};

/** Fallback floor/ceiling used when a column has no explicit override. */
export const HOLDINGS_TABLE_MIN_WIDTH = 72;
export const HOLDINGS_TABLE_MAX_WIDTH = 480;

export const HOLDINGS_TABLE_COLUMN_MIN_WIDTHS: Record<HoldingsTableColumnId, number> = {
	security_symbol: 160,
	account_name: 110,
	quantity: 90,
	average_cost: 110,
	latest_price: 110,
	total_value: 130,
	profit_loss: 120,
	profit_loss_percent: 90
};

export const HOLDINGS_TABLE_COLUMN_MAX_WIDTHS: Record<HoldingsTableColumnId, number> = {
	security_symbol: 360,
	account_name: 280,
	quantity: 180,
	average_cost: 220,
	latest_price: 220,
	total_value: 260,
	profit_loss: 240,
	profit_loss_percent: 160
};

export type HoldingsTableConfig = {
	widths: Record<HoldingsTableColumnId, number>;
	visible: HoldingsTableColumnId[];
};

export const HOLDINGS_TABLE_DEFAULT_CONFIG: HoldingsTableConfig = {
	widths: { ...HOLDINGS_TABLE_DEFAULT_WIDTHS },
	visible: [...HOLDINGS_TABLE_COLUMN_IDS]
};

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isColumnId(value: unknown): value is HoldingsTableColumnId {
	return (
		typeof value === 'string' && (HOLDINGS_TABLE_COLUMN_IDS as readonly string[]).includes(value)
	);
}

/** Clamps a width to the column's bounds; non-finite input falls back to the default. */
export function clampColumnWidth(id: HoldingsTableColumnId, width: number): number {
	const min = HOLDINGS_TABLE_COLUMN_MIN_WIDTHS[id] ?? HOLDINGS_TABLE_MIN_WIDTH;
	const max = HOLDINGS_TABLE_COLUMN_MAX_WIDTHS[id] ?? HOLDINGS_TABLE_MAX_WIDTH;
	if (!Number.isFinite(width)) return HOLDINGS_TABLE_DEFAULT_WIDTHS[id] ?? min;
	return Math.min(Math.max(Math.round(width), min), max);
}

/**
 * Turns an arbitrary stored value into a usable config:
 * - missing/invalid input → defaults (all columns visible, default widths)
 * - unknown column ids are dropped, widths clamped to the column bounds
 * - remaining columns keep canonical order, and the sticky first column is
 *   always visible.
 */
export function normalizeHoldingsTableConfig(raw: unknown): HoldingsTableConfig {
	const widths: Record<HoldingsTableColumnId, number> = { ...HOLDINGS_TABLE_DEFAULT_WIDTHS };
	let visible: HoldingsTableColumnId[] = [...HOLDINGS_TABLE_COLUMN_IDS];

	if (!isRecord(raw)) {
		return { widths, visible };
	}

	if (isRecord(raw.widths)) {
		for (const id of HOLDINGS_TABLE_COLUMN_IDS) {
			const value = raw.widths[id];
			if (typeof value === 'number' && Number.isFinite(value)) {
				widths[id] = clampColumnWidth(id, value);
			}
		}
	}

	if (Array.isArray(raw.visible)) {
		const requested = new Set(raw.visible.filter(isColumnId));
		if (requested.size > 0) {
			visible = HOLDINGS_TABLE_COLUMN_IDS.filter(
				(id) => requested.has(id) || id === HOLDINGS_TABLE_STICKY_COLUMN_ID
			);
		}
	}

	return { widths, visible };
}

const numberFormatter = new Intl.NumberFormat('en-CA', {
	minimumFractionDigits: 2,
	maximumFractionDigits: 2
});

/**
 * Formats a valuation price range as "lower – upper" (e.g. "20.00 – 50.00")
 * using 2 decimal places and an en dash separator.
 * Returns an em dash ("—") if either bound is missing, null, undefined, or non-finite.
 */
export function formatValuationRange(
	lowerBound?: number | null,
	upperBound?: number | null
): string {
	if (
		typeof lowerBound !== 'number' ||
		!Number.isFinite(lowerBound) ||
		typeof upperBound !== 'number' ||
		!Number.isFinite(upperBound)
	) {
		return '—';
	}

	return `${numberFormatter.format(lowerBound)} \u2013 ${numberFormatter.format(upperBound)}`;
}

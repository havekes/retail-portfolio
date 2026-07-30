/**
 * Quantity-weighted blended average cost across holdings.
 *
 * Returns 0 when there are no holdings or total quantity is 0.
 * Treats missing `average_cost` as 0.
 */
export function blendedAverageCost(
	holdings: { quantity: number; average_cost?: number }[]
): number {
	if (holdings.length === 0) return 0;

	const totalQuantity = holdings.reduce((sum, h) => sum + h.quantity, 0);
	if (totalQuantity === 0) return 0;

	const totalCost = holdings.reduce((sum, h) => sum + h.quantity * (h.average_cost ?? 0), 0);
	return totalCost / totalQuantity;
}

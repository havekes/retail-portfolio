<script lang="ts">
	import type { Candle } from '$lib/utils/finance/candle';
	import { cn } from '$lib/utils';

	interface Props {
		data?: (number | Candle)[];
		width?: number | string;
		height?: number;
		strokeWidth?: number;
		color?: string;
		positiveColor?: string;
		negativeColor?: string;
		isPositive?: boolean;
		showArea?: boolean;
		class?: string;
		id?: string;
		ariaLabel?: string;
	}

	let {
		data = [],
		width = '100%',
		height = 32,
		strokeWidth = 1.5,
		color,
		positiveColor = '#10b981',
		negativeColor = '#f43f5e',
		isPositive,
		showArea = true,
		class: className = '',
		id,
		ariaLabel = 'Price sparkline'
	}: Props = $props();

	// Generate deterministic fallback ID per component instance
	const defaultId = `sparkline-grad-${Math.random().toString(36).slice(2, 9)}`;
	const gradientId = $derived(id ?? defaultId);

	const values = $derived.by(() => {
		if (!data || data.length === 0) return [];
		return data
			.map((item) => {
				if (typeof item === 'number') return item;
				if (item && typeof item === 'object' && 'close' in item && typeof item.close === 'number') {
					return item.close;
				}
				return null;
			})
			.filter((v): v is number => v !== null && !isNaN(v));
	});

	const trendIsPositive = $derived.by(() => {
		if (typeof isPositive === 'boolean') {
			return isPositive;
		}
		if (values.length >= 2) {
			return values[values.length - 1] >= values[0];
		}
		return true;
	});

	const trendColor = $derived(color ?? (trendIsPositive ? positiveColor : negativeColor));

	const vbWidth = 100;
	const vbHeight = $derived(typeof height === 'number' ? height : 32);

	const pathData = $derived.by(() => {
		if (values.length === 0) {
			return { linePath: '', areaPath: '' };
		}

		const padY = Math.max(strokeWidth, 2);
		const padX = strokeWidth / 2;
		const effectiveW = vbWidth - 2 * padX;
		const effectiveH = vbHeight - 2 * padY;

		if (values.length === 1) {
			const midY = vbHeight / 2;
			const linePath = `M 0 ${midY.toFixed(2)} L ${vbWidth} ${midY.toFixed(2)}`;
			const areaPath = `M 0 ${midY.toFixed(2)} L ${vbWidth} ${midY.toFixed(2)} L ${vbWidth} ${vbHeight} L 0 ${vbHeight} Z`;
			return { linePath, areaPath };
		}

		const minVal = Math.min(...values);
		const maxVal = Math.max(...values);
		const range = maxVal - minVal;

		const points = values.map((val, i) => {
			const x = padX + (i / (values.length - 1)) * effectiveW;
			const y = range === 0 ? vbHeight / 2 : padY + (1 - (val - minVal) / range) * effectiveH;
			return { x, y };
		});

		if (values.length === 2) {
			const linePath = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)} L ${points[1].x.toFixed(2)} ${points[1].y.toFixed(2)}`;
			const areaPath = `${linePath} L ${points[1].x.toFixed(2)} ${vbHeight} L ${points[0].x.toFixed(2)} ${vbHeight} Z`;
			return { linePath, areaPath };
		}

		// Smooth Catmull-Rom to Cubic Bezier curve
		let linePath = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;

		for (let i = 0; i < points.length - 1; i++) {
			const p0 = points[Math.max(0, i - 1)];
			const p1 = points[i];
			const p2 = points[i + 1];
			const p3 = points[Math.min(points.length - 1, i + 2)];

			const cp1x = p1.x + (p2.x - p0.x) / 6;
			const cp1y = Math.min(Math.max(p1.y + (p2.y - p0.y) / 6, padY / 2), vbHeight - padY / 2);
			const cp2x = p2.x - (p3.x - p1.x) / 6;
			const cp2y = Math.min(Math.max(p2.y - (p3.y - p1.y) / 6, padY / 2), vbHeight - padY / 2);

			linePath += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
		}

		const lastPoint = points[points.length - 1];
		const firstPoint = points[0];
		const areaPath = `${linePath} L ${lastPoint.x.toFixed(2)} ${vbHeight} L ${firstPoint.x.toFixed(2)} ${vbHeight} Z`;

		return { linePath, areaPath };
	});
</script>

<svg
	viewBox="0 0 {vbWidth} {vbHeight}"
	{width}
	{height}
	preserveAspectRatio="none"
	role="img"
	aria-label={ariaLabel}
	class={cn('block overflow-visible', className)}
>
	<defs>
		<linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
			<stop offset="0%" stop-color={trendColor} stop-opacity="0.35" />
			<stop offset="100%" stop-color={trendColor} stop-opacity="0.0" />
		</linearGradient>
	</defs>
	{#if showArea && pathData.areaPath}
		<path d={pathData.areaPath} fill="url(#{gradientId})" />
	{/if}
	{#if pathData.linePath}
		<path
			d={pathData.linePath}
			fill="none"
			stroke={trendColor}
			stroke-width={strokeWidth}
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
	{/if}
</svg>

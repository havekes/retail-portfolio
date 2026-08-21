<script lang="ts">
	let {
		size = 24,
		class: className = '',
		...restProps
	}: {
		size?: number | string;
		class?: string;
		[key: string]: unknown;
	} = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="2"
	stroke-linecap="round"
	stroke-linejoin="round"
	class={className}
	{...restProps}
>
	<line x1="3" y1="4" x2="21" y2="4" />
	<line x1="3" y1="9" x2="21" y2="9" />
	<line x1="3" y1="15" x2="21" y2="15" />
	<line x1="3" y1="20" x2="21" y2="20" />
	<polyline points="5 18 11 8 19 14" stroke-dasharray="2 2" />
</svg>

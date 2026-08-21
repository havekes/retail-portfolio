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
	<line x1="3" y1="5" x2="21" y2="5" />
	<line x1="3" y1="10" x2="21" y2="10" />
	<line x1="3" y1="15" x2="21" y2="15" />
	<line x1="3" y1="20" x2="21" y2="20" />
	<line x1="6" y1="20" x2="18" y2="5" stroke-dasharray="2 2" />
</svg>

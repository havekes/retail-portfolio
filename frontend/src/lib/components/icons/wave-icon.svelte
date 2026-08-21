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
	<path d="M3 18 L7 6 L12 15 L17 8 L21 16" />
</svg>

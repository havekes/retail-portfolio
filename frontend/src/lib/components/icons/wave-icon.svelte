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
	<path d="M2 20 L6 13 L10 16 L15 7 L18 10 L22 4" />
</svg>

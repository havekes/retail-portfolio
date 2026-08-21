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
	<path d="M8 3v4" />
	<rect x="6" y="7" width="4" height="7" rx="1" />
	<path d="M8 14v7" />
	<path d="M16 3v7" />
	<rect x="14" y="10" width="4" height="7" rx="1" />
	<path d="M16 17v4" />
</svg>

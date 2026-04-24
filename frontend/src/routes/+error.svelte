<script lang="ts">
	import { page } from '$app/stores';
	import { resolve } from '$app/paths';
</script>

<div class="flex min-h-screen flex-col items-center justify-center p-4 text-center">
	<h1 class="mb-4 text-6xl font-bold text-gray-800 dark:text-gray-200">
		{$page.status}
	</h1>
	<p class="mb-8 text-xl text-gray-600 dark:text-gray-400">
		{$page.error?.message || 'Something went wrong'}
	</p>
	<a
		href={resolve('/')}
		class="rounded-md bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
	>
		Go back home
	</a>
</div>

<script lang="ts">
	import AppHeader from '$lib/components/layout/app-header.svelte';
	import SecuritySettings from '$lib/components/security/security-settings.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Security Settings</title>
</svelte:head>

<div class="flex h-full flex-col">
	<AppHeader title="Security settings" subtitle="Manage two-factor authentication and passkeys" />
	<div class="flex-1 overflow-y-auto">
		<SecuritySettings initialStatus={data.status} initialPasskeys={data.passkeys} />
	</div>
</div>

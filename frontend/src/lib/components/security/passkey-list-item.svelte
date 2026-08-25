<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import ConfirmationModal from '$lib/components/ui/confirmation-modal/confirmation-modal.svelte';
	import PasskeyRenameModal from './passkey-rename-modal.svelte';
	import type { PasskeyResponse } from '$lib/api/types/security';
	import { getSecurityService } from './securityService.svelte';
	import { formatDate } from '$lib/utils/date';
	import Fingerprint from '@lucide/svelte/icons/fingerprint';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Loader2 from '@lucide/svelte/icons/loader-2';

	let {
		passkey
	}: {
		passkey: PasskeyResponse;
	} = $props();

	const securityService = getSecurityService();

	let showRenameModal = $state(false);
	let showDeleteModal = $state(false);
	let isDeleting = $state(false);

	async function handleDelete() {
		isDeleting = true;
		try {
			await securityService.deletePasskey(passkey.id);
		} catch (err) {
			console.error('Failed to delete passkey', err);
		} finally {
			isDeleting = false;
		}
	}
</script>

<div
	class="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
>
	<div class="flex items-start gap-3">
		<div class="mt-0.5 rounded-md border bg-muted/50 p-2 text-foreground">
			<Fingerprint class="h-5 w-5" />
		</div>
		<div class="space-y-1">
			<div class="flex flex-wrap items-center gap-2">
				<h4 class="font-medium text-foreground">{passkey.name}</h4>
				{#if passkey.transports && passkey.transports.length > 0}
					{#each passkey.transports as transport (transport)}
						<Badge variant="outline" class="text-[10px] uppercase">{transport}</Badge>
					{/each}
				{/if}
			</div>
			<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
				<span>Created {formatDate(passkey.created_at)}</span>
				<span>•</span>
				<span>
					{passkey.last_used_at ? `Last used ${formatDate(passkey.last_used_at)}` : 'Never used'}
				</span>
			</div>
		</div>
	</div>

	<div class="flex items-center gap-2 self-end sm:self-auto">
		<Button
			variant="ghost"
			size="sm"
			onclick={() => (showRenameModal = true)}
			title="Rename passkey"
		>
			<Pencil class="mr-1 h-3.5 w-3.5" />
			Rename
		</Button>
		<Button
			variant="ghost"
			size="sm"
			class="text-destructive hover:bg-destructive/10 hover:text-destructive"
			onclick={() => (showDeleteModal = true)}
			disabled={isDeleting}
			title="Delete passkey"
		>
			{#if isDeleting}
				<Loader2 class="h-3.5 w-3.5 animate-spin" />
			{:else}
				<Trash2 class="mr-1 h-3.5 w-3.5" />
				Delete
			{/if}
		</Button>
	</div>
</div>

<PasskeyRenameModal bind:open={showRenameModal} {passkey} />

<ConfirmationModal
	bind:open={showDeleteModal}
	title="Delete passkey"
	description={`Are you sure you want to delete "${passkey.name}"? You will no longer be able to use it to sign in.`}
	onconfirm={handleDelete}
/>

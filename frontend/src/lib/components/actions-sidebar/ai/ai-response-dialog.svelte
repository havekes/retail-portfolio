<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import Copy from '@lucide/svelte/icons/copy';
	import Save from '@lucide/svelte/icons/save';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import { notesService } from '$lib/api/notesService';
	import { ModalState } from '@/utils/modal-state.svelte';

	interface AIAnalysisData {
		title: string;
		content: string | null;
		isLoading: boolean;
		actionId: string;
		error: string | null;
	}

	let { modalState, onRetry, securityId } = $props<{
		modalState: ModalState<AIAnalysisData>;
		onRetry?: () => void;
		securityId: string;
	}>();

	let copySuccess = $state(false);
	let saveSuccess = $state(false);

	async function copyToClipboard() {
		if (!modalState.data?.content) return;
		await navigator.clipboard.writeText(modalState.data.content);
		copySuccess = true;
		setTimeout(() => (copySuccess = false), 2000);
	}

	async function saveAsNote() {
		if (!modalState.data?.content || !securityId) return;
		try {
			await notesService.createNote(securityId, {
				content: `AI Analysis (${modalState.data.title}):\n\n${modalState.data.content}`
			});
			saveSuccess = true;
			setTimeout(() => (saveSuccess = false), 2000);
		} catch (error) {
			console.error('Failed to save note:', error);
		}
	}

	function formatContent(text: string) {
		if (!text) return '';
		// Basic formatting: bold, bullets, headings
		return text
			.replace(/^### (.*$)/gm, '<h3 class="text-lg font-bold mt-4 mb-2">$1</h3>')
			.replace(/^## (.*$)/gm, '<h2 class="text-xl font-bold mt-6 mb-3">$1</h2>')
			.replace(/^# (.*$)/gm, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>')
			.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
			.replace(/^\* (.*$)/gm, '<li class="ml-4 list-disc">$1</li>')
			.replace(/^- (.*$)/gm, '<li class="ml-4 list-disc">$1</li>')
			.split('\n\n')
			.map((p) => {
				if (p.startsWith('<h') || p.startsWith('<li')) return p;
				return `<p class="mb-4 leading-relaxed text-muted-foreground">${p}</p>`;
			})
			.join('');
	}
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="max-w-2xl">
			<Dialog.Header>
				<Dialog.Title>{modalState.data?.title}</Dialog.Title>
				<Dialog.Description>
					{#if modalState.data?.isLoading}
						Generating analysis...
					{:else}
						AI-powered security analysis
					{/if}
				</Dialog.Description>
			</Dialog.Header>

			<div class="mt-4 max-h-[60vh] overflow-y-auto rounded-md bg-accent/30 p-4">
				{#if modalState.data?.isLoading}
					<div class="flex flex-col items-center justify-center py-12 text-muted-foreground">
						<Loader2 class="h-8 w-8 animate-spin" />
						<p class="mt-4 text-sm">Our AI is analyzing the security data...</p>
					</div>
				{:else if modalState.data?.content}
					<div class="prose prose-sm dark:prose-invert">
						<!-- eslint-disable-next-line svelte/no-at-html-tags -->
						{@html formatContent(modalState.data.content)}
					</div>
				{:else if modalState.data?.error}
					<div class="flex flex-col items-center justify-center py-12 text-muted-foreground">
						<p class="text-sm text-destructive">{modalState.data.error}</p>
						{#if onRetry}
							<Button variant="outline" size="sm" class="mt-4" onclick={onRetry}>
								<RotateCcw class="mr-2 h-4 w-4" />
								Retry
							</Button>
						{/if}
					</div>
				{:else}
					<div class="flex flex-col items-center justify-center py-12 text-muted-foreground">
						<p class="text-sm">Something went wrong. Please try again.</p>
						{#if onRetry}
							<Button variant="outline" size="sm" class="mt-4" onclick={onRetry}>
								<RotateCcw class="mr-2 h-4 w-4" />
								Retry
							</Button>
						{/if}
					</div>
				{/if}
			</div>

			<Dialog.Footer class="mt-6 flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2">
				{#if !modalState.data?.isLoading && modalState.data?.content}
					<div class="flex flex-1 gap-2">
						<Button variant="ghost" size="sm" onclick={copyToClipboard} disabled={copySuccess}>
							{#if copySuccess}
								Copied!
							{:else}
								<Copy class="mr-2 h-4 w-4" />
								Copy to Clipboard
							{/if}
						</Button>
						<Button variant="ghost" size="sm" onclick={saveAsNote} disabled={saveSuccess}>
							{#if saveSuccess}
								Saved as Note!
							{:else}
								<Save class="mr-2 h-4 w-4" />
								Save as Note
							{/if}
						</Button>
					</div>
				{/if}
				<Button variant="ghost" size="sm" onclick={() => modalState.close()}>Close</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>

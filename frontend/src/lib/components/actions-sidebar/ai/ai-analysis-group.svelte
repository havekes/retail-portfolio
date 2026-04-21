<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import Brain from '@lucide/svelte/icons/brain';
	import FileText from '@lucide/svelte/icons/file-text';
	import MessageSquare from '@lucide/svelte/icons/message-square';
	import AIResponseDialog from './ai-response-dialog.svelte';
	import { aiService } from '$lib/api/aiService';
	import { ModalState } from '@/utils/modal-state.svelte';
	import GroupTitle from '../group-title.svelte';

	let { securityId, expanded = $bindable(false) } = $props<{
		securityId: string;
		expanded?: boolean;
	}>();

	interface AIAnalysisData {
		title: string;
		content: string | null;
		isLoading: boolean;
		actionId: string;
		error: string | null;
	}

	const responseModal = new ModalState<AIAnalysisData>();

	const aiActions = [
		{
			id: 'fundamentals',
			label: 'Explain Fundamentals',
			description: "Get AI analysis of this company's fundamentals",
			icon: Brain
		},
		{
			id: 'summarize-notes',
			label: 'Summarize Notes',
			description: 'AI summary of your notes for this security',
			icon: FileText
		},
		{
			id: 'portfolio-debate',
			label: 'Portfolio Debate',
			description: 'AI analysis vs your portfolio holdings',
			icon: MessageSquare
		}
	];

	async function handleRequestAnalysis(actionId: string) {
		const action = aiActions.find((a) => a.id === actionId);
		if (!action) return;

		responseModal.open({
			title: action.label,
			content: null,
			isLoading: true,
			actionId: actionId,
			error: null
		});

		try {
			let response;
			if (actionId === 'fundamentals') {
				response = await aiService.analyzeFundamentals(securityId);
			} else if (actionId === 'summarize-notes') {
				response = await aiService.summarizeNotes(securityId);
			} else if (actionId === 'portfolio-debate') {
				response = await aiService.analyzePortfolioFit(securityId, {
					portfolio_context: 'Analyzing in isolation for now.'
				});
			}

			if (response && responseModal.data) {
				responseModal.data.content = response.content;
				responseModal.data.isLoading = false;
			}
		} catch (error) {
			console.error('AI analysis failed:', error);
			if (responseModal.data) {
				responseModal.data.error = error instanceof Error ? error.message : 'Analysis failed';
				responseModal.data.isLoading = false;
			}
		}
	}

	function handleRetry() {
		if (responseModal.data?.actionId) {
			handleRequestAnalysis(responseModal.data.actionId);
		}
	}
</script>

<Sidebar.Group>
	<GroupTitle {expanded} onToggle={() => (expanded = !expanded)}>AI Analysis</GroupTitle>

	{#if expanded}
		<Sidebar.GroupContent>
			<div class="space-y-1">
				{#each aiActions as action (action.id)}
					<button
						onclick={() => handleRequestAnalysis(action.id)}
						class="flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
					>
						<action.icon class="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
						<div class="space-y-0.5">
							<div class="font-medium">{action.label}</div>
							<div class="text-xs text-muted-foreground">{action.description}</div>
						</div>
					</button>
				{/each}
			</div>
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>

{#if responseModal.data}
	<AIResponseDialog modalState={responseModal} onRetry={handleRetry} {securityId} />
{/if}

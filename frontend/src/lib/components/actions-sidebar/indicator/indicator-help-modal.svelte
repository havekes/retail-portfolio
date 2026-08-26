<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';

	let {
		open = $bindable(false),
		indicatorId = null
	}: {
		open?: boolean;
		indicatorId?: string | null;
	} = $props();

	interface HelpContent {
		title: string;
		subtitle: string;
		description: string;
		interpretation: string[];
		components?: { name: string; desc: string }[];
	}

	const HELP_DATA: Record<string, HelpContent> = {
		macd: {
			title: 'Moving Average Convergence Divergence (MACD)',
			subtitle: 'Momentum & Trend-Following Indicator',
			description:
				'MACD tracks the relationship between two exponential moving averages (typically the 12-period and 26-period EMAs). A 9-period EMA called the signal line is plotted alongside to identify potential momentum shifts and trend reversals.',
			components: [
				{ name: 'MACD Line', desc: 'The 12-period EMA minus the 26-period EMA.' },
				{ name: 'Signal Line', desc: 'A 9-period EMA of the MACD line.' },
				{
					name: 'Histogram',
					desc: 'Visualizes the distance between the MACD line and the signal line. Green bars indicate positive (bullish) momentum; red bars indicate negative (bearish) momentum.'
				}
			],
			interpretation: [
				'Bullish Signal: The MACD line crosses above the signal line.',
				'Bearish Signal: The MACD line crosses below the signal line.',
				'Centerline Crossover: MACD crossing above zero indicates upward momentum; crossing below zero indicates downward momentum.',
				'Divergence: When price hits higher highs while MACD prints lower highs (or vice versa), signaling possible trend exhaustion.'
			]
		},
		bb: {
			title: 'Bollinger Bands',
			subtitle: 'Volatility & Range Channel Indicator',
			description:
				'Bollinger Bands consist of a center Simple Moving Average (typically 20 periods) bounded by upper and lower standard deviation bands (typically ±2 standard deviations). They expand and contract based on market volatility.',
			components: [
				{
					name: 'Middle Band',
					desc: '20-period simple moving average (SMA) representing the baseline trend.'
				},
				{ name: 'Upper Band', desc: 'Middle band + (2 × standard deviation).' },
				{ name: 'Lower Band', desc: 'Middle band - (2 × standard deviation).' }
			],
			interpretation: [
				'The Squeeze: When bands contract tightly together, volatility is low. This frequently precedes a sharp breakout move.',
				'Overbought / Oversold: Prices touching or exceeding the upper band suggest relatively high prices; touching the lower band suggests relatively low prices.',
				'Band Walking: In strong directional trends, price often "walks" along the upper or lower band without immediately reversing.'
			]
		},
		rsi: {
			title: 'Relative Strength Index (RSI)',
			subtitle: 'Momentum Oscillator (0 to 100)',
			description:
				'RSI measures the speed and change of price movements on a scale from 0 to 100 (standard 14-period lookback). It helps traders identify overbought and oversold conditions.',
			components: [
				{
					name: 'Overbought Level (70)',
					desc: 'Readings above 70 indicate an asset may be overbought or overextended and due for a pullback.'
				},
				{
					name: 'Oversold Level (30)',
					desc: 'Readings below 30 indicate an asset may be oversold or undervalued and ripe for a rebound.'
				},
				{
					name: 'Centerline (50)',
					desc: 'Readings above 50 confirm net bullish momentum; readings below 50 confirm net bearish momentum.'
				}
			],
			interpretation: [
				'Overbought/Oversold Reversals: Watch for RSI crossing back below 70 or rising back above 30 as potential entry/exit triggers.',
				'Bullish Divergence: Price forms lower lows while RSI forms higher lows, signaling weakening selling pressure.',
				'Bearish Divergence: Price forms higher highs while RSI forms lower highs, signaling waning buying momentum.'
			]
		},
		obv: {
			title: 'On-Balance Volume (OBV)',
			subtitle: 'Cumulative Volume Flow Momentum',
			description:
				'On-Balance Volume is a cumulative momentum indicator that relates volume to price change. Volume is added on up days and subtracted on down days, tracking institutional money flow before major price moves appear.',
			components: [
				{
					name: 'Cumulative Volume Line',
					desc: 'A running sum where positive volume accompanies price gains and negative volume accompanies price drops.'
				}
			],
			interpretation: [
				'Trend Confirmation: A rising OBV confirms a price uptrend; a falling OBV confirms a price downtrend.',
				'Breakouts: When OBV breaks out to new highs or lows ahead of price, it often foreshadows an upcoming price breakout.',
				'Divergence: If price is rising while OBV is falling or flat, the price advance lacks volume conviction and may reverse.'
			]
		}
	};

	let content = $derived(indicatorId ? (HELP_DATA[indicatorId] ?? null) : null);
</script>

<Dialog.Root bind:open>
	<Dialog.Content
		class="max-h-[85vh] overflow-y-auto sm:max-w-lg"
		data-testid="indicator-help-modal"
	>
		<Dialog.Header>
			<Dialog.Title>{content?.title ?? 'Indicator Information'}</Dialog.Title>
			{#if content?.subtitle}
				<Dialog.Description class="text-xs font-medium text-muted-foreground">
					{content.subtitle}
				</Dialog.Description>
			{/if}
		</Dialog.Header>

		{#if content}
			<div class="space-y-4 py-2 text-sm">
				<div>
					<h4 class="mb-1 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
						Overview
					</h4>
					<p class="text-xs leading-relaxed text-foreground sm:text-sm">{content.description}</p>
				</div>

				{#if content.components && content.components.length > 0}
					<div>
						<h4 class="mb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
							Key Components
						</h4>
						<ul class="space-y-1.5">
							{#each content.components as item (item.name)}
								<li class="rounded bg-muted/40 p-2 text-xs">
									<span class="font-semibold text-foreground">{item.name}:</span>
									<span class="ml-1 text-muted-foreground">{item.desc}</span>
								</li>
							{/each}
						</ul>
					</div>
				{/if}

				<div>
					<h4 class="mb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
						How to Interpret
					</h4>
					<ul class="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
						{#each content.interpretation as tip (tip)}
							<li><span class="text-foreground">{tip}</span></li>
						{/each}
					</ul>
				</div>
			</div>
		{/if}

		<Dialog.Footer>
			<Button
				type="button"
				variant="outline"
				onclick={() => (open = false)}
				data-testid="help-modal-close-btn"
			>
				Close
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

Coding Agent Guide: retail-portfolio (Frontend)

## Project Overview

`retail-portfolio` is a portfolio tracker designed for the retail investor.

**Frontend Tech Stack**:

- Svelte 5 / SvelteKit
- TypeScript
- TailwindCSS v4
- Vite
- npm package manager

## Infrastructure

- Docker Compose for dev environment

## Development Workflow

**ALWAYS**: Execute frontend commands in `retail-portfolio-frontend`.

**Frontend Workflow (`docker exec retail-portfolio-frontend`)**:

1. Install dependencies: `npm install`
2. Lint and format code: `npm run lint`
3. Run type checks: `npm run check`
4. Format code: `npm run format`

**MANDATORY**: When writing or editing code, **ALWAYS** run linting, type checks, and format before submitting.

## Architecture Guidelines

### 1. Core Architecture: Separation of Concerns

- **`.svelte` files are for UI**: Keep markup, styling, and simple component-level view state in `.svelte` files.
- **`.svelte.ts` files are for Logic**: Extract complex state, business logic, and API interactions into standard TypeScript files utilizing Svelte 5 Runes.

### 2. State Management: Default to ES6 Classes

When generating stateful logic, always default to ES6 Classes instead of returning objects with manual getters/setters or using legacy `svelte/store`.

Classes natively support Svelte 5 Runes, eliminating boilerplate and making the code substantially easier to reason about, mock, and extend.

#### ✅ The Standard Pattern

Define properties with `$state` directly inside the class. The Svelte compiler automatically handles the underlying proxying.

```typescript
// ReceiptService.svelte.ts
export class ReceiptService {
	// State properties (no getters needed)
	isParsing = $state(false);
	parsedData = $state<ReceiptData | null>(null);
	error = $state<string | null>(null);

	// Derived state
	hasValidData = $derived(this.parsedData !== null && !this.error);

	// Methods
	async parseImage(imageBlob: Blob) {
		this.isParsing = true;
		this.error = null;
		try {
			// e.g., Vision LLM API call
			this.parsedData = await api.extractDetails(imageBlob);
		} catch (err) {
			this.error = 'Failed to extract receipt data.';
		} finally {
			this.isParsing = false;
		}
	}
}
```

### 3. The Critical Gotchas (Must Enforce)

#### 🚨 Gotcha 1: NEVER Destructure Primitives

When consuming a reactive class or object in a `.svelte` file, do not destructure its primitive properties. Destructuring severs the proxy connection, and the variables will instantly lose their reactivity.

❌ **BAD (Loses reactivity):**

```svelte
<script lang="ts">
	import { ReceiptService } from './ReceiptService.svelte.ts';
	const service = new ReceiptService();

	// Reactivity is broken! isParsing will freeze at its initial value.
	let { isParsing, parsedData } = service;
</script>
```

✅ **GOOD (Maintains reactivity):**

```svelte
<script lang="ts">
	import { ReceiptService } from './ReceiptService.svelte.ts';
	const service = new ReceiptService();
</script>

{#if service.isParsing}
	<p>Processing image...</p>
{/if}
```

#### 🚨 Gotcha 2: SSR Data Bleed (No Global Instances)

Never export an instantiated class or a raw `$state` variable directly from a `.svelte.ts` module if the application uses Server-Side Rendering (SSR). This will cause state to bleed across different users' requests.

❌ **BAD (Cross-request contamination):**

```typescript
// auth.svelte.ts
export const authService = new AuthService(); // DANGEROUS IN SSR!
```

✅ **GOOD (Context API Injection):**

Always instantiate the class inside a component layout and pass it down via the Context API.

```svelte
<script lang="ts">
	import { setContext } from 'svelte';
	import { ReceiptService } from './ReceiptService.svelte.ts';

	setContext('receiptService', new ReceiptService());
</script>
```

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import type { ReceiptService } from './ReceiptService.svelte.ts';

	const service = getContext<ReceiptService>('receiptService');
</script>
```

#### 🚨 Gotcha 3: Reassigning Objects vs. Mutating

Svelte 5's `$state` deeply proxies objects and arrays. You can freely mutate inner properties or push to arrays, and the UI will update. However, be mindful that replacing the entire object reference requires the variable itself to be declared with `$state`.

```typescript
let items = $state([]);

// ✅ Works: Deep proxy catches the mutation
items.push(newItem);

// ✅ Works: Top-level reassignment is caught by the $state declaration
items = [...items, newItem];
```

### 4. Derived State and Effects

- **Use `$derived(expression)`** to compute values based on `$state`. It caches the result and only recalculates when dependencies change.
- **Use `$effect(() => {...})`** exclusively for side effects (e.g., syncing to localStorage, manipulating the DOM, or setting up event listeners). Do not use `$effect` to synchronize state; use `$derived` or update state directly in event handlers.

### 5. Backend Logic Orchestration (Stateless vs. Stateful)

To maintain clarity and scalability, split backend logic into two distinct layers.

#### Layer 1: Stateless API Clients (`/src/lib/api/`)

These are pure TypeScript files (not `.svelte.ts`). Their only job is to handle HTTP requests, headers, authentication, and raw data parsing. They know nothing about the UI or Svelte reactivity.

Organize these by external domain or integration.

```typescript
// src/lib/api/paperless.ts
export const paperlessClient = {
	async getRecentReceipts(): Promise<Blob[]> {
		const res = await fetch('/api/paperless/documents?tags=receipt');
		if (!res.ok) throw new Error('Failed to fetch from Paperless-ngx');
		// ... return blobs
	}
};

// src/lib/api/firefly.ts
export const fireflyClient = {
	async createTransaction(data: any) {
		const res = await fetch('/api/firefly/transactions', {
			method: 'POST',
			body: JSON.stringify(data)
		});
		if (!res.ok) throw new Error('Failed to import to Firefly III');
		return res.json();
	}
};
```

#### Layer 2: Stateful Svelte Services (`/src/lib/services/`)

These are your `.svelte.ts` classes. They import the stateless API clients, orchestrate the business logic (e.g., fetching a receipt, sending it to a vision LLM, and pushing the result to your finance tracker), and expose `$state` to the UI.

```typescript
// src/lib/services/ReceiptSyncService.svelte.ts
import { paperlessClient } from '../api/paperless';
import { fireflyClient } from '../api/firefly';
// Import your vision LLM client here

export class ReceiptSyncService {
	isProcessing = $state(false);
	currentStep = $state<string | null>(null);
	errors = $state<string[]>([]);

	async processLatestReceipts() {
		this.isProcessing = true;
		this.errors = [];

		try {
			this.currentStep = 'Fetching from Paperless...';
			const receipts = await paperlessClient.getRecentReceipts();

			for (const receipt of receipts) {
				this.currentStep = 'Extracting data via Vision LLM...';
				// const extractedData = await visionClient.parse(receipt);

				this.currentStep = 'Importing to Firefly III...';
				// await fireflyClient.createTransaction(extractedData);
			}

			this.currentStep = 'Sync complete!';
		} catch (err) {
			this.errors.push(err instanceof Error ? err.message : 'Unknown error');
		} finally {
			this.isProcessing = false;
		}
	}
}
```

#### 🚨 Gotcha 4: Error State Granularity

When generating backend call logic, do not just use a generic `error = $state(false)`. Always store the actual error message strings or objects so the UI can provide actionable feedback. Network requests fail often; the service must handle these gracefully without crashing the component.

#### 🚨 Gotcha 5: Avoid "Waterfall" Fetching in Components

Do not trigger sequential API calls inside a `.svelte` file's `$effect` block. If step B depends on step A, orchestrate that flow entirely inside an async method in your Service class (as shown in the `processLatestReceipts` example above). The component should only ever call `service.doTheThing()` and react to the resulting `$state` changes.

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

### 1. Layer 1: The UI Layer (`.svelte` files)

**Concept**: Keep `.svelte` files focused on markup, styling, and simple component-level view state. Push complex logic out to the service layer.

**Code Example:**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import type { DataService } from '$lib/services/DataService.svelte';

	// Retrieve the service instance from context
	const dataService = getContext<DataService>('dataService');
</script>

{#if dataService.isLoading}
	<p>Loading...</p>
{:else}
	<button onclick={() => dataService.fetchItems()}> Load Items </button>
	<ul>
		{#each dataService.items as item}
			<li>{item.name}</li>
		{/each}
	</ul>
{/if}
```

#### 🚨 Gotcha 1: Never Destructure Primitives

When consuming a reactive class or object, do not destructure its primitive properties. Destructuring severs the proxy connection, instantly breaking reactivity. Always access them directly on the object instance (e.g., use `dataService.isLoading` instead of `let { isLoading } = dataService`).

#### 🚨 Gotcha 2: Misusing Effects

Use `$effect` exclusively for side effects like syncing to `localStorage`, manipulating the DOM, or setting up event listeners. Do not use `$effect` to synchronize state or trigger data fetches. Use `$derived` for computed state, or update state directly in event handlers.

### 2. Layer 2: The State & Service Layer (`.svelte.ts` files)

**Concept**: Extract complex state, business logic, and API orchestration into standard TypeScript files utilizing Svelte 5 Runes. Always default to ES6 Classes instead of returning objects with manual getters/setters or using legacy `svelte/store`.

**Code Example:**

```typescript
import { apiClient } from '$lib/api/apiClient';

export class DataService {
	// State properties (no getters needed)
	items = $state<Array<{ id: number; name: string }>>([]);
	isLoading = $state(false);
	errorMessage = $state<string | null>(null);

	// Derived state
	hasItems = $derived(this.items.length > 0);

	// Orchestration method
	async fetchItems() {
		this.isLoading = true;
		this.errorMessage = null;
		try {
			this.items = await apiClient.getItems();
		} catch (error) {
			this.errorMessage = error instanceof Error ? error.message : 'Unknown error';
		} finally {
			this.isLoading = false;
		}
	}
}
```

#### 🚨 Gotcha 3: SSR Data Bleed (No Global Instances)

Never export an instantiated class or a raw `$state` variable directly from a `.svelte.ts` module. In a Server-Side Rendering environment, this causes state to bleed across different users' requests. Always instantiate the class inside a component or layout (`+layout.svelte`) and pass it down via `setContext` and `getContext`.

#### 🚨 Gotcha 4: Reassigning Objects vs. Mutating

Svelte 5 deeply proxies objects and arrays declared with `$state`. You can freely mutate inner properties or push to arrays (`this.items.push(newItem)`), and the UI will update. However, if you reassign the entire array or object reference (`this.items = newArray`), the class property itself must be declared with `$state` to maintain reactivity.

### 3. Layer 3: The API & Backend Communication Layer (`.ts` files)

**Concept**: Separate raw backend communication from your reactive Svelte state. Create stateless API clients in pure `.ts` files. Their only job is to handle HTTP requests, headers, and raw data parsing.

**Code Example:**

```typescript
export const apiClient = {
	async getItems() {
		const response = await fetch('/api/items');

		if (!response.ok) {
			throw new Error(`Failed to fetch items: ${response.statusText}`);
		}

		return response.json();
	}
};
```

#### 🚨 Gotcha 5: Error State Granularity

When handling backend calls in your service class, do not use a generic boolean error state. Always catch and store the actual error message strings or objects so the UI layer can provide actionable feedback to the user.

#### 🚨 Gotcha 6: Avoid Waterfall Fetching in Components

Do not trigger sequential API calls directly inside a `.svelte` file. If step B depends on step A, orchestrate that multi-step flow entirely inside a single async method in your Service class (Layer 2). The UI component should only ever call `service.performAction()` and react to the state.

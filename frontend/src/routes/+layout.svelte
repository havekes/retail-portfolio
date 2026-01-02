<script lang="ts">
  import '../app.css';
  // import favicon from '$lib/assets/favicon.svg';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores'; // Pour accéder à l'URL actuelle
  import { userStore } from '$lib/stores/userStore';
  import type { User } from '$lib/types/user';

  let { children } = $props();

  let user: User | null = $state(null);
  userStore.subscribe((u) => (user = u));

  function shouldRedirect() {
    const currentPath = $page.url.pathname;
    return !user && currentPath !== '/login' && currentPath !== '/signup';
  }

  $effect(() => {
    if (shouldRedirect()) {
      goto('/login');
    }
  });
</script>

<svelte:head>
  <!-- <link rel="icon" href={favicon} /> -->
</svelte:head>

{@render children()}
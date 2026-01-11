<script lang="ts">
	import { userStore } from '$lib/stores/userStore';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	userStore.clearUser();

	goto(resolve('/login'));
</script>

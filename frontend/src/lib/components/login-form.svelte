<script lang="ts">
  import { Button } from "$lib/components/ui/button/index.js";
  import * as Card from "$lib/components/ui/card/index.js";
  import { Input } from "$lib/components/ui/input/index.js";
  import {
    FieldGroup,
    Field,
    FieldLabel,
    FieldDescription,
  } from "$lib/components/ui/field/index.js";
<<<<<<< HEAD
  import { authService } from "$lib/services/authService";
  import { userStore } from "$lib/stores/userStore";

  const id = $props.id();

  let email = $state('');
  let password = $state('');
  let isLoading = $state(false);
  let error = $state<string | null>(null);

  async function handleSubmit(event: Event) {
    event.preventDefault();
    isLoading = true;
    error = null;

    try {
<<<<<<< HEAD
      const response = await authService.login({ email, password });
      userStore.setUser(response.user, response.access_token);
=======
      const response = await authService.login(email, password);
      userStore.setUser(response.user);
      // Ici, tu peux rediriger ou gérer le succès, e.g., navigate('/dashboard');
>>>>>>> 6019a5f (setup front for login)
    } catch (err) {
      error = 'Login failed. Please check your credentials.';
    } finally {
      isLoading = false;
    }
  }
</script>

=======
  const id = $props.id();
</script>
>>>>>>> a29a120 (all front elements)
<Card.Root class="mx-auto w-full max-w-sm">
  <Card.Header>
    <Card.Title class="text-2xl">Login</Card.Title>
    <Card.Description>Enter your email below to login to your account</Card.Description>
  </Card.Header>
  <Card.Content>
<<<<<<< HEAD
<<<<<<< HEAD
    <form onsubmit={handleSubmit}>
=======
    <form on:submit={handleSubmit}>
>>>>>>> 6019a5f (setup front for login)
      <FieldGroup>
        <Field>
          <FieldLabel for="email-{id}">Email</FieldLabel>
          <Input 
            id="email-{id}" 
            type="email" 
            placeholder="m@example.com" 
            required 
            bind:value={email} 
          />
=======
    <form>
      <FieldGroup>
        <Field>
          <FieldLabel for="email-{id}">Email</FieldLabel>
          <Input id="email-{id}" type="email" placeholder="m@example.com" required />
>>>>>>> a29a120 (all front elements)
        </Field>
        <Field>
          <div class="flex items-center">
            <FieldLabel for="password-{id}">Password</FieldLabel>
<<<<<<< HEAD
          </div>
          <Input 
            id="password-{id}" 
            type="password" 
            required 
            bind:value={password} 
          />
        </Field>
        {#if error}
          <p class="text-red-500 text-sm">{error}</p>
        {/if}
        <Field>
          <Button type="submit" class="w-full" disabled={isLoading}>
            {isLoading ? 'Logging in...' : 'Login'}
          </Button>
          <FieldDescription class="text-center">
            Don't have an account? <a href="/signup">Sign up</a>
=======
            <a href="##" class="ml-auto inline-block text-sm underline">
              Forgot your password?
            </a>
          </div>
          <Input id="password-{id}" type="password" required />
        </Field>
        <Field>
          <Button type="submit" class="w-full">Login</Button>
          <FieldDescription class="text-center">
            Don't have an account? <a href="##">Sign up</a>
>>>>>>> a29a120 (all front elements)
          </FieldDescription>
        </Field>
      </FieldGroup>
    </form>
  </Card.Content>
</Card.Root>
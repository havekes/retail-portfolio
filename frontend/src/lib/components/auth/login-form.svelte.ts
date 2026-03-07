import { goto } from '$app/navigation';
import { authService } from '$lib/services/authService';
import { userStore } from '$lib/stores/userStore';
import { resolve } from '$app/paths';
import { APIError } from '$lib/services/baseService';

export class LoginFormState {
	email = $state('');
	password = $state('');
	isLoading = $state(false);
	error = $state<string | null>(null);

	handleSubmit = async (event: Event) => {
		event.preventDefault();
		this.isLoading = true;
		this.error = null;

		try {
			const response = await authService.login({ email: this.email, password: this.password });
			userStore.setUser(response.user, response.access_token);
			goto(resolve('/'));
		} catch (error) {
			if (error instanceof APIError && error.status === 403) {
				this.error = 'Email not verified. Please check your inbox for a verification link.';
			} else {
				this.error = 'Login failed. Please check your credentials.';
			}
		} finally {
			this.isLoading = false;
		}
	};
}

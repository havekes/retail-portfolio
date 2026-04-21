import { authService } from '$lib/api/authService';
import { ApiError } from '$lib/api/apiClient';

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
			await authService.login({ email: this.email, password: this.password });
			window.location.href = '/';
		} catch (error) {
			if (error instanceof ApiError && error.status === 403) {
				this.error = 'Email not verified. Please check your inbox for a verification link.';
			} else {
				this.error = 'Login failed. Please check your credentials.';
			}
		} finally {
			this.isLoading = false;
		}
	};
}

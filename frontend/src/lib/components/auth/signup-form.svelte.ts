import { goto } from '$app/navigation';
import { authService } from '$lib/services/authService';
import { APIError } from '$lib/services/baseService';
import { resolve } from '$app/paths';

export class SignupFormState {
	email = $state('');
	password = $state('');
	confirmPassword = $state('');
	isLoading = $state(false);
	error = $state<string | null>(null);

	handleSubmit = async (event: Event) => {
		event.preventDefault();
		this.isLoading = true;
		this.error = null;

		if (this.password !== this.confirmPassword) {
			this.error = 'Passwords do not match.';
			this.isLoading = false;
			return;
		}

		try {
			await authService.signup({ email: this.email, password: this.password });
			goto(resolve('/auth/signup/confirmation'));
		} catch (error) {
			if (error instanceof APIError && error.status === 409) {
				this.error = 'Account with this email already exists.';
			} else {
				this.error = 'Signup failed. Please try again.';
			}
		} finally {
			this.isLoading = false;
		}
	};
}

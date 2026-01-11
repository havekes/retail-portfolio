import { writable } from 'svelte/store';
import type { User } from '$lib/types/user';

export interface AuthState {
	user: User | null;
	token: string | null;
}

export const userStore = (() => {
	const initialState: AuthState = {
		user: null,
		token: null
	};

	// Load from sessionStorage at startup
	const storedToken = sessionStorage.getItem('auth_token');
	const storedUser = sessionStorage.getItem('auth_user');
	if (storedToken && storedUser) {
		try {
			initialState.token = storedToken;
			initialState.user = JSON.parse(storedUser);
		} catch (error) {
			console.error('Error when parsing session stored user data', error);
			sessionStorage.removeItem('auth_token');
			sessionStorage.removeItem('auth_user');
		}
	}

	const { subscribe, update } = writable<AuthState>(initialState);

	const setUser = (user: User, token: string) => {
		update((state) => {
			state.user = user;
			state.token = token;
			sessionStorage.setItem('auth_token', token);
			sessionStorage.setItem('auth_user', JSON.stringify(user));
			return state;
		});
	};

	const clearUser = () => {
		update((state) => {
			state.user = null;
			state.token = null;
			sessionStorage.removeItem('auth_token');
			sessionStorage.removeItem('auth_user');
			return state;
		});
	};

	const getToken = () => {
		let token: string | null = null;
		subscribe((state) => {
			token = state.token;
		})();
		return token;
	};

	return {
		subscribe,
		setUser,
		clearUser,
		getToken
	};
})();

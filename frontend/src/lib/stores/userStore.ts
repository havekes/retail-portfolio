import { writable } from 'svelte/store';
<<<<<<< HEAD
import type { User } from '$lib/types/user';

export interface AuthState {
  user: User | null;
  token: string | null;
}

export const userStore = (() => {
  const initialState: AuthState = {
    user: null,
    token: null,
  };

  // Charger depuis sessionStorage au démarrage
  const storedToken = sessionStorage.getItem('auth_token');
  const storedUser = sessionStorage.getItem('auth_user');
  if (storedToken && storedUser) {
    try {
      initialState.token = storedToken;
      initialState.user = JSON.parse(storedUser);
    } catch (error) {
      console.error('Erreur lors du chargement depuis sessionStorage:', error);
      sessionStorage.removeItem('auth_token');
      sessionStorage.removeItem('auth_user');
    }
  }

  const { subscribe, set, update } = writable<AuthState>(initialState);

  return {
    subscribe,
    setUser: (user: User, token: string) => {
      update(state => {
        state.user = user;
        state.token = token;
        sessionStorage.setItem('auth_token', token);
        sessionStorage.setItem('auth_user', JSON.stringify(user));
        return state;
      });
    },
    clearUser: () => {
      update(state => {
        state.user = null;
        state.token = null;
        sessionStorage.removeItem('auth_token');
        sessionStorage.removeItem('auth_user');
        return state;
      });
    },
    getToken: () => {
      let token: string | null = null;
      subscribe(state => {
        token = state.token;
      })();
      return token;
    },
=======

export interface User {
  id: number;
  email: string;
  name: string;
}

export const userStore = (() => {
  const { subscribe, set, update } = writable<User | null>(null);

  return {
    subscribe,
    setUser: (user: User) => set(user),
    clearUser: () => set(null),
>>>>>>> 6019a5f (setup front for login)
  };
})();
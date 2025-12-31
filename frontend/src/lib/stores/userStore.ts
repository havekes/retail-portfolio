import { writable } from 'svelte/store';

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
  };
})();
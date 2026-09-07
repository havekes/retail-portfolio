import { SvelteMap } from 'svelte/reactivity';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastOptions {
	duration?: number;
	type?: ToastType;
}

export interface Toast {
	id: string;
	message: string;
	type: ToastType;
	duration: number;
}

export class ToastState {
	toasts = $state<Toast[]>([]);
	private defaultDuration = 4000;
	private timers = new SvelteMap<string, ReturnType<typeof setTimeout>>();

	add(message: string, options?: ToastOptions): string;
	add(item: { message: string; type?: ToastType; duration?: number }): string;
	add(
		messageOrItem: string | { message: string; type?: ToastType; duration?: number },
		options?: ToastOptions
	): string {
		const message = typeof messageOrItem === 'string' ? messageOrItem : messageOrItem.message;
		const type =
			typeof messageOrItem === 'object' && messageOrItem.type
				? messageOrItem.type
				: (options?.type ?? 'info');
		const duration =
			typeof messageOrItem === 'object' && messageOrItem.duration !== undefined
				? messageOrItem.duration
				: (options?.duration ?? this.defaultDuration);

		const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

		const item: Toast = {
			id,
			message,
			type,
			duration
		};

		this.toasts.push(item);

		if (duration > 0) {
			const timer = setTimeout(() => {
				this.remove(id);
			}, duration);
			this.timers.set(id, timer);
		}

		return id;
	}

	remove(id: string): void {
		const timer = this.timers.get(id);
		if (timer) {
			clearTimeout(timer);
			this.timers.delete(id);
		}
		this.toasts = this.toasts.filter((t) => t.id !== id);
	}

	clear(): void {
		for (const timer of this.timers.values()) {
			clearTimeout(timer);
		}
		this.timers.clear();
		this.toasts = [];
	}

	success(message: string, options?: Omit<ToastOptions, 'type'>): string {
		return this.add(message, { ...options, type: 'success' });
	}

	error(message: string, options?: Omit<ToastOptions, 'type'>): string {
		return this.add(message, { ...options, type: 'error' });
	}

	info(message: string, options?: Omit<ToastOptions, 'type'>): string {
		return this.add(message, { ...options, type: 'info' });
	}

	warning(message: string, options?: Omit<ToastOptions, 'type'>): string {
		return this.add(message, { ...options, type: 'warning' });
	}
}

export const toast = new ToastState();

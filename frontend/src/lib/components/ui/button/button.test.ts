import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import Button from './button.svelte';
import { buttonVariants } from './button.svelte';

describe('Button', () => {
	it('includes active:translate-y-px by default and sets data-button-press="true"', () => {
		render(Button, {
			props: {
				'aria-label': 'Click me'
			}
		});
		const btn = screen.getByRole('button', { name: 'Click me' });
		expect(btn).toHaveAttribute('data-button-press', 'true');
		expect(btn.classList.contains('active:translate-y-px')).toBe(true);
		expect(btn.classList.contains('active:translate-y-0')).toBe(false);
	});

	it('retains active:translate-y-px on popup triggers without not-aria-[haspopup]', () => {
		render(Button, {
			props: {
				'aria-label': 'Menu',
				'aria-haspopup': 'menu'
			}
		});
		const btn = screen.getByRole('button', { name: 'Menu' });
		expect(btn.classList.contains('active:translate-y-px')).toBe(true);
		expect(btn.className).not.toContain('not-aria-[haspopup]');
	});

	it('disables press animation when pressEffect is false', () => {
		render(Button, {
			props: {
				'aria-label': 'No press',
				pressEffect: false
			}
		});
		const btn = screen.getByRole('button', { name: 'No press' });
		expect(btn).toHaveAttribute('data-button-press', 'false');
		expect(btn.classList.contains('active:translate-y-0')).toBe(true);
	});

	it('disables press animation when data-button-press="false" is set', () => {
		render(Button, {
			props: {
				'aria-label': 'No press attr',
				'data-button-press': 'false'
			}
		});
		const btn = screen.getByRole('button', { name: 'No press attr' });
		expect(btn).toHaveAttribute('data-button-press', 'false');
		expect(btn.classList.contains('active:translate-y-0')).toBe(true);
	});

	it('buttonVariants supports pressable: false', () => {
		const classes = buttonVariants({ pressable: false });
		expect(classes).toContain('active:translate-y-0');
	});
});

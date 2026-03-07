/// <reference types="vitest" />
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), '');

	return {
		plugins: [tailwindcss(), sveltekit(), svelteTesting()],
		resolve: {
			alias: {
				$lib: '/app/src/lib' // Assurez-vous que ça pointe vers le bon chemin
			}
		},
		server: {
			host: '0.0.0.0',
			port: 8100,
			allowedHosts: env.VITE_ALLOWED_HOSTS ? env.VITE_ALLOWED_HOSTS.split(',') : []
		},
		test: {
			environment: 'jsdom',
			setupFiles: ['./src/setupTest.ts'],
			include: ['src/**/*.{test,spec}.{js,ts}']
		}
	};
});

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
			environmentOptions: {
				url: 'http://localhost/'
			},
			setupFiles: ['./src/setupTest.ts'],
			include: ['src/**/*.{test,spec}.{js,ts}'],

			// --- Token-Saving Output Flags ---
			reporters: ['dot'], // Replaces multi-line blocks with single dots (.)
			silent: 'passed-only', // Mutes console.log for passing tests; keeps logs on failure
			bail: 1, // Stop immediately on 1st failure to preserve context
			printConsoleTrace: false, // Suppresses stack traces for console logs

			// --- Coverage Setup ---
			coverage: {
				provider: 'v8',
				include: ['src/**/*.{js,ts}'],
				reporter: ['json'], // Generates JSON coverage without terminal tables
				skipFull: true // Omits files with 100% coverage to reduce JSON size
			}
		}
	};
});

import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	resolve: {
		alias: {
			$lib: '/app/src/lib' // Assurez-vous que ça pointe vers le bon chemin
		}
	},
	server: {
		host: '0.0.0.0',
		port: 8100
	}
});

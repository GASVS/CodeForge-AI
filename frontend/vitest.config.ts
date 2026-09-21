import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Vitest config (P2.4). Vite picks this up automatically when running vitest.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
    include: ['src/**/*.test.{ts,tsx}', 'components/**/*.test.{ts,tsx}'],
  },
});

import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'hsl(var(--bg))',
        panel: 'hsl(var(--panel))',
        text: 'hsl(var(--text))',
        muted: 'hsl(var(--muted))',
        line: 'hsl(var(--line))',
        primary: 'hsl(var(--primary))',
        danger: 'hsl(var(--danger))',
        success: 'hsl(var(--success))',
        warning: 'hsl(var(--warning))',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(16, 24, 40, 0.08)',
      },
      borderRadius: {
        xl: '0.75rem',
      },
    },
  },
  plugins: [],
} satisfies Config;

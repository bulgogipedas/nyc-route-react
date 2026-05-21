/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#000000',
        canvas: '#FFFFFF',
        'accent-magenta': '#FF33CC',
        'surface-soft': '#F5F5F5',
        hairline: '#E6E6E6',
        'hairline-soft': '#F0F0F0',
        'block-lime': '#D2FF00',
        'block-lilac': '#E7E2F9',
        'block-cream': '#FFF8E5',
        'block-mint': '#D1FADD',
        'block-pink': '#FFD1E6',
        'block-coral': '#FFCEC2',
        'block-navy': '#00003C',
        ink: '#000000',
        'inverse-ink': '#FFFFFF',
        'inverse-canvas': '#000000',
      },
      fontFamily: {
        sans: ['Inter', 'SF Pro Display', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Menlo', 'monospace'],
      },
      borderRadius: {
        xs: '2px',
        sm: '6px',
        md: '8px',
        lg: '24px',
        xl: '32px',
        pill: '50px',
      },
      spacing: {
        hair: '1px',
        section: '96px',
      },
      letterSpacing: {
        'display-xl': '-1.72px',
        'display-lg': '-0.96px',
        'headline': '-0.26px',
        'eyebrow': '0.54px',
        'caption': '0.60px',
      },
      fontWeight: {
        '320': '320',
        '330': '330',
        '340': '340',
        '400': '400',
        '450': '450',
        '480': '480',
        '540': '540',
      }
    },
  },
  plugins: [],
}

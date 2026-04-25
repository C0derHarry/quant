/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          base:     '#07090D',
          surface:  '#0D1117',
          elevated: '#161B22',
          overlay:  '#1C2128',
        },
        border: {
          subtle:  '#161B22',
          DEFAULT: '#21262D',
          strong:  '#30363D',
        },
        ink: {
          primary:   '#E6EDF3',
          secondary: '#8B949E',
          muted:     '#6E7681',
          disabled:  '#484F58',
        },
        gain:    '#3FB950',
        loss:    '#F85149',
        warn:    '#D29922',
        accent:  '#388BFD',
        violet:  '#BC8CFF',
        teal:    '#39D353',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', { lineHeight: '14px', letterSpacing: '0.06em' }],
        xs:    ['11px', { lineHeight: '16px' }],
        sm:    ['12px', { lineHeight: '18px' }],
        base:  ['13px', { lineHeight: '20px' }],
        md:    ['14px', { lineHeight: '22px' }],
        lg:    ['16px', { lineHeight: '24px' }],
        xl:    ['18px', { lineHeight: '28px' }],
        '2xl': ['22px', { lineHeight: '32px' }],
        '3xl': ['28px', { lineHeight: '36px' }],
        '4xl': ['36px', { lineHeight: '44px' }],
      },
      borderRadius: {
        sm:  '3px',
        DEFAULT: '5px',
        md:  '7px',
        lg:  '10px',
        xl:  '14px',
      },
      boxShadow: {
        card:       '0 1px 3px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.04)',
        'card-lg':  '0 4px 16px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.04)',
        glow:       '0 0 20px rgba(56,139,253,.18)',
        'glow-gain':'0 0 14px rgba(63,185,80,.2)',
        'glow-loss':'0 0 14px rgba(248,81,73,.2)',
      },
      animation: {
        'fade-up':   'fadeUp .25s ease-out',
        'fade-in':   'fadeIn .2s ease-out',
        'pulse-dot': 'pulseDot 2s ease-in-out infinite',
      },
      keyframes: {
        fadeUp: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseDot: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%':      { opacity: '.4', transform: 'scale(.8)' },
        },
      },
    },
  },
  plugins: [],
}

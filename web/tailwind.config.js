/** @type {import('tailwindcss').Config} */
// Every colour is a CSS variable (defined per theme in src/styles/main.css) so light, dark and high-contrast
// themes swap by changing one attribute on <html>. Never write a hex value in a template.
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,html}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: token('bg'),            // page background (cassava cream)
        surface: token('surface'),  // cards
        'surface-2': token('surface-2'),
        ink: token('ink'),          // text and headers (deep forest)
        'ink-soft': token('ink-soft'),
        leaf: token('leaf'),        // actions and healthy fills (not for text)
        'leaf-ink': token('leaf-ink'), // healthy text
        sun: token('sun'),          // highlights and the mic
        clay: token('clay'),        // problems and warnings, fills only
        'clay-ink': token('clay-ink'), // warning text
        line: token('line'),
      },
      fontFamily: { sans: ['"Atkinson Hyperlegible"', 'system-ui', 'sans-serif'] },
      // Fluid sizes. Body at least 20px and headings at least 28px at the default text size; they scale with the
      // user's text-size setting because --text-scale multiplies the root font size.
      fontSize: {
        body: ['clamp(1.25rem, 1.15rem + 0.5vw, 1.4rem)', { lineHeight: '1.55' }],
        small: ['clamp(1.05rem, 1rem + 0.2vw, 1.15rem)', { lineHeight: '1.5' }],
        h3: ['clamp(1.4rem, 1.2rem + 1vw, 1.75rem)', { lineHeight: '1.25' }],
        h2: ['clamp(1.75rem, 1.4rem + 1.6vw, 2.25rem)', { lineHeight: '1.2' }],
        h1: ['clamp(2rem, 1.5rem + 2.4vw, 3rem)', { lineHeight: '1.12' }],
      },
      borderRadius: { seed: '1rem', pod: '0.75rem', leaf: '0.75rem' },
      transitionTimingFunction: {
        // Motion language (docs/design-and-motion-guide.md section 3)
        spring: 'cubic-bezier(.34, 1.3, .5, 1)',
        'spring-soft': 'cubic-bezier(.2, .9, .25, 1.1)',
      },
      minHeight: { tap: '3.5rem' }, // 56px touch targets
      minWidth: { tap: '3.5rem' },
    },
  },
  plugins: [],
};

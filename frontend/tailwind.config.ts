import type { Config } from "tailwindcss";

// Colours come from CSS variables in src/styles/theme.css.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: token("color-primary"),
          foreground: token("color-primary-foreground"),
        },
        accent: {
          DEFAULT: token("color-accent"),
          foreground: token("color-accent-foreground"),
        },
        background: token("color-background"),
        surface: {
          DEFAULT: token("color-surface"),
          2: token("color-surface-2"),
        },
        foreground: token("color-foreground"),
        muted: token("color-muted"),
        border: token("color-border"),
        ring: token("color-ring"),
        success: token("color-success"),
        warning: token("color-warning"),
        danger: token("color-danger"),
        info: token("color-info"),
        conf: {
          high: token("color-conf-high"),
          medium: token("color-conf-medium"),
          low: token("color-conf-low"),
        },
        rain: {
          0: token("rain-0"),
          1: token("rain-1"),
          2: token("rain-2"),
          3: token("rain-3"),
          4: token("rain-4"),
          5: token("rain-5"),
        },
        alert: {
          yellow: token("alert-yellow"),
          orange: token("alert-orange"),
          red: token("alert-red"),
          "on-yellow": token("alert-on-yellow"),
          "on-orange": token("alert-on-orange"),
          "on-red": token("alert-on-red"),
        },
        qr: {
          fg: token("qr-fg"),
          bg: token("qr-bg"),
        },
        temp: {
          1: token("temp-1"),
          2: token("temp-2"),
          3: token("temp-3"),
          4: token("temp-4"),
          5: token("temp-5"),
        },
      },
      borderColor: {
        DEFAULT: token("color-border"),
      },
      borderRadius: {
        card: "var(--radius)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 220ms ease-out both",
      },
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "var(--font-telugu)",
          "var(--font-devanagari)",
          "system-ui",
          "sans-serif",
        ],
        telugu: ["var(--font-telugu)", "var(--font-inter)", "sans-serif"],
        devanagari: ["var(--font-devanagari)", "var(--font-inter)", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;

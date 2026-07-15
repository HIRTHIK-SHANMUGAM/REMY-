/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Tokens resolve to CSS vars (see globals.css) so they switch with the
        // light/dark theme; the RGB-channel form keeps opacity modifiers (/15).
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          hover: "rgb(var(--accent-hover) / <alpha-value>)",
          from: "rgb(var(--accent-from) / <alpha-value>)",
          to: "rgb(var(--accent-to) / <alpha-value>)",
          soft: "rgb(var(--accent-soft) / <alpha-value>)",
        },
        surface: {
          0: "rgb(var(--surface-0) / <alpha-value>)",
          1: "rgb(var(--surface-1) / <alpha-value>)",
          2: "rgb(var(--surface-2) / <alpha-value>)",
          3: "rgb(var(--surface-3) / <alpha-value>)",
        },
        ink: {
          DEFAULT: "rgb(var(--ink) / <alpha-value>)",
          muted: "rgb(var(--ink-muted) / <alpha-value>)",
          faint: "rgb(var(--ink-faint) / <alpha-value>)",
        },
      },
      boxShadow: {
        bubble: "0 1px 2px rgba(0,0,0,0.25)",
        "accent-glow": "0 4px 16px -4px rgba(59,130,246,0.45)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        blink: { "0%, 100%": { opacity: "0.2" }, "50%": { opacity: "1" } },
      },
      animation: {
        "fade-in": "fade-in 0.18s ease-out",
        blink: "blink 1.2s infinite",
      },
    },
  },
  plugins: [],
};

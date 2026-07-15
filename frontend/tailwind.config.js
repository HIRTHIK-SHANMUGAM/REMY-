/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Mobbin-inspired: clean neutrals + one confident accent.
        accent: {
          DEFAULT: "#3b82f6",
          hover: "#2563eb",
          from: "#4f8cf7", // gradient start (bubbles, logo)
          to: "#2f6bd8", // gradient end
          soft: "#1e3a8a",
        },
        surface: {
          0: "#0a0e13", // app background (slightly deeper)
          1: "#111823", // panels / REMY bubbles
          2: "#19212d", // raised / input
          3: "#263140", // borders / hover
        },
        ink: {
          DEFAULT: "#e8eef4",
          muted: "#95a3b1", // brighter for AA contrast
          faint: "#6b7a89", // brighter than before (was #5b6875)
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

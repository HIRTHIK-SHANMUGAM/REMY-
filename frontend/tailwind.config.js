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
          soft: "#1e3a8a",
        },
        surface: {
          0: "#0b0f14", // app background
          1: "#111820", // panels / REMY bubbles
          2: "#1a242f", // raised / input
          3: "#243040", // borders / hover
        },
        ink: {
          DEFAULT: "#e6edf3",
          muted: "#8b98a5",
          faint: "#5b6875",
        },
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

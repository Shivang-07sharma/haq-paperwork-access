import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1b1a17", soft: "#4a463f", faint: "#7a746a" },
        sand: { DEFAULT: "#f6f2ea", deep: "#ece5d8", line: "#ddd4c3" },
        indigo: { deep: "#1f3b6e", mid: "#2f5596", light: "#e8eef8" },
        moss: { deep: "#1f5f3f", mid: "#2f8558", light: "#e3f2e9" },
        amber: { deep: "#8a5a11", mid: "#c98a20", light: "#fbf0d9" },
        clay: { deep: "#8a2f21", mid: "#c25139", light: "#fbe8e3" },
      },
      fontSize: {
        base: ["1.0625rem", { lineHeight: "1.65" }],
        lg: ["1.1875rem", { lineHeight: "1.6" }],
        xl: ["1.375rem", { lineHeight: "1.45" }],
      },
      borderRadius: { xl: "0.9rem", "2xl": "1.25rem" },
      boxShadow: { card: "0 1px 2px rgba(27,26,23,.06), 0 6px 18px -8px rgba(27,26,23,.18)" },
    },
  },
  plugins: [],
};

export default config;

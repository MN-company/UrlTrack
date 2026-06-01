import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "#FF6D00",
        border: "#2A2A2A",
        ink: "#F5F5F5",
        live: "#00C853",
        muted: "#888888",
        obsidian: "#0A0A0A",
        panel: "#141414",
        raised: "#1C1C1C",
        signal: "#3BA7FF",
        violet: "#A47CFF"
      },
      fontFamily: {
        body: ["var(--font-body)", "sans-serif"],
        display: ["var(--font-display)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"]
      },
      borderRadius: {
        ui: "8px"
      }
    }
  },
  plugins: []
};

export default config;

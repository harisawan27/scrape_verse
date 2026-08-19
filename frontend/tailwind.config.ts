import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        space: {
          950: "#07090E",
          900: "#0B0F19",
          850: "#0E1424",
          800: "#131B2E",
          750: "#19243C",
          700: "#22314E",
          600: "#334568",
        },
        radar: {
          cyan: "#06B6D4",
          emerald: "#10B981",
          amber: "#F59E0B",
          rose: "#F43F5E",
          indigo: "#6366F1",
          purple: "#A855F7",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "ping-slow": "ping 2.5s cubic-bezier(0, 0, 0.2, 1) infinite",
        "radar-spin": "spin 8s linear infinite",
      },
      boxShadow: {
        glow: "0 0 25px -5px rgba(6, 182, 212, 0.25)",
        "glow-emerald": "0 0 25px -5px rgba(16, 185, 129, 0.25)",
        "glow-rose": "0 0 25px -5px rgba(244, 63, 94, 0.25)",
        "glow-indigo": "0 0 25px -5px rgba(99, 102, 241, 0.25)",
        "glow-amber": "0 0 25px -5px rgba(245, 158, 11, 0.25)",
      },
    },
  },
  plugins: [],
};

export default config;

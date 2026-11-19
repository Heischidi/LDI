import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./hooks/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: "#0B1F3A",
          50: "#EEF2F7",
          100: "#D5E0EC",
          700: "#13315C",
          800: "#0B1F3A",
          900: "#071426",
        },
        brand: {
          DEFAULT: "#0F5132",
          light: "#198754",
          muted: "#E8F5EE",
        },
      },
    },
  },
  plugins: [],
};

export default config;

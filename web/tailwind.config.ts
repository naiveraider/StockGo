import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        yahooBlue: "#1a76d2",
        yahooBg: "#f2f4f6"
      }
    }
  },
  plugins: []
};

export default config;


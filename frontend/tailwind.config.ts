import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "./providers/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        muted: "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))",
        surface: "hsl(var(--surface))",
        primary: "hsl(var(--primary))",
        "primary-foreground": "hsl(var(--primary-foreground))",
        warning: "hsl(var(--warning))",
        destructive: "hsl(var(--destructive))",
        success: "hsl(var(--success))"
      },
      borderRadius: {
        lg: "8px",
        md: "6px",
        sm: "4px"
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "sans-serif"]
      },
      boxShadow: {
        panel: "0 1px 2px rgb(15 23 42 / 0.06), 0 12px 32px rgb(15 23 42 / 0.04)"
      }
    }
  },
  plugins: []
};

export default config;


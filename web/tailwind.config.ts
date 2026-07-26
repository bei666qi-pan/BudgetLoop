import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "#F7FAFF",
        foreground: "#0B1F44",
        surface: "#FFFFFF",
        "surface-hover": "#F4F8FF",
        muted: "#EDF4FF",
        "muted-foreground": "#60759A",
        border: "#D8E4F5",
        "border-strong": "#BED2EE",
        accent: "#1769F6",
        "accent-foreground": "#FFFFFF",
        "accent-glow": "rgba(23,105,246,.12)",
        destructive: "#EF4B5B",
        "destructive-foreground": "#FFFFFF",
        ring: "#1769F6",
        success: "#0CAD72",
        warning: "#F28A00",
        info: "#2F7DF6",
        critical: "#EF4B5B",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "SFMono-Regular", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["0.75rem", { lineHeight: "1.1rem" }],
        xs: ["0.8125rem", { lineHeight: "1.2rem" }],
        sm: ["0.875rem", { lineHeight: "1.35rem" }],
        base: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.0625rem", { lineHeight: "1.6rem" }],
        xl: ["1.25rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.625rem", { lineHeight: "2rem" }],
        "3xl": ["2.125rem", { lineHeight: "2.45rem" }],
      },
      borderRadius: { sm: "6px", DEFAULT: "8px", md: "10px", lg: "12px", xl: "16px" },
      boxShadow: {
        surface: "0 10px 30px rgba(35,89,160,.08)",
        elevated: "0 18px 50px rgba(35,89,160,.14)",
        control: "0 4px 14px rgba(35,89,160,.06)",
      },
      animation: {
        "fade-in": "fadeIn 180ms ease-out",
        "slide-up": "slideUp 200ms cubic-bezier(.16,1,.3,1)",
        "pulse-subtle": "pulseSubtle 2s ease-in-out infinite",
        in: "fadeIn 160ms ease-out",
      },
      keyframes: {
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        pulseSubtle: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".5" } },
      },
      transitionDuration: { fast: "160ms", DEFAULT: "200ms", slow: "300ms" },
    },
  },
  plugins: [],
};

export default config;

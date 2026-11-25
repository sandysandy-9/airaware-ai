/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        navy: {
          950: "#060b17",
          900: "#0b1528",
          850: "#0f1c35",
          800: "#142544",
          700: "#1e3760",
          600: "#2d4e84",
        },
        aqi: {
          good: "#10B981",         // 0 - 50
          satisfactory: "#84CC16", // 51 - 100
          moderate: "#EAB308",     // 101 - 200
          poor: "#F97316",         // 201 - 300
          verypoor: "#EF4444",     // 301 - 400
          severe: "#7F1D1D",       // 401 - 500
        }
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

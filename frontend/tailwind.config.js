/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        // Sistema gráfico SCI
        sci: {
          DEFAULT: "#00964B", // Verde principal (RGB 0,149,48 → #00964B)
          verde: "#00964B",
          "verde-oscuro": "#007539",
          amarillo: "#FFD100", // Acento principal
          oro: "#FAB500", // Oro / naranja secundario
          naranja: "#F28F00",
        },
      },
    },
  },
  plugins: [],
};

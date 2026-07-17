export default {
    content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                // Fixed dark greyscale palette with light blue accents only for focus/actions
                shell: {
                    bg: '#111214',
                    panel: '#1a1b1f',
                    border: '#2c2e35',
                    text: '#e3e4e8',
                    muted: '#8f949d',
                },
                accent: {
                    DEFAULT: '#7dd3fc',
                    hover: '#60c5f8',
                    dim: '#0ea5e9',
                },
            },
        },
    },
    plugins: [],
};

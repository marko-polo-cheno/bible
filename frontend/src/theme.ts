import { createTheme, MantineColorsTuple } from '@mantine/core';

// Olive — brand primary. #B4B792 / #95A37F / #646E57 / #424236
const olive: MantineColorsTuple = [
  '#F4F5EF',
  '#E7E9DC',
  '#D3D7C0',
  '#B4B792',
  '#A4AC87',
  '#95A37F',
  '#646E57',
  '#57604B',
  '#424236',
  '#33352B',
];

// Almond — warm accent. #EED9C4 / #704820, blossom tones for highlights
const almond: MantineColorsTuple = [
  '#FBF5EE',
  '#EED9C4',
  '#E4C6A8',
  '#D8B28C',
  '#C99A6D',
  '#B78351',
  '#9C6636',
  '#704820',
  '#5A3A1A',
  '#452C14',
];

export const theme = createTheme({
  primaryColor: 'olive',
  colors: { olive, almond },
  fontFamily:
    "'Sora', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif",
  headings: {
    fontFamily: "'Sora', -apple-system, sans-serif",
    fontWeight: '600',
  },
  defaultRadius: 'md',
  cursorType: 'pointer',
  components: {
    Button: { defaultProps: { radius: 'xl' } },
    Modal: { defaultProps: { radius: 'lg' } },
  },
});

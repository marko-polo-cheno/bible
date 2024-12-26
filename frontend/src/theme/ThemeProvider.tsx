import { ReactNode } from 'react';
import {
  Accordion,
  Button,
  Checkbox,
  Combobox,
  createTheme,
  Image,
  MantineProvider,
  Menu,
  Notification,
  Popover,
  Select,
  Skeleton,
  Tabs,
  Tooltip,
} from '@mantine/core';

const theme = createTheme({
  primaryColor: 'mark',
  focusRing: 'auto',
  defaultRadius: 'xl',
  cursorType: 'pointer',
  colors: {
    mark: [
      '#f4eeff',
      '#e3daf7',
      '#c4b1ea',
      '#a485dd',
      '#8861d2',
      '#f4eeff',
      '#e3daf7',
      '#c4b1ea',
      '#a485dd',
      '#8861d2',
    ],
    ice: [
      '#deffff',
      '#cafeff',
      '#99faff',
      '#64f8ff',
      '#3df5fe',
      '#deffff',
      '#cafeff',
      '#99faff',
      '#64f8ff',
      '#3df5fe',
    ],
  },
  components: {
    Checkbox: Checkbox.extend({
      defaultProps: {
        radius: 'sm',
      },
    }),
    Tabs: Tabs.extend({
      defaultProps: {
        radius: 'md',
      },
    }),
    Image: Image.extend({
      defaultProps: {
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-expect-error
        // This works, but unfortunately TS still complains. See GH Issue: https://github.com/mantinedev/mantine/issues/7106
        draggable: false,
      },
    }),
    Tooltip: Tooltip.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Popover: Popover.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Notification: Notification.extend({
      defaultProps: {
        radius: 'lg',
        withBorder: true,
      },
    }),
    Button: Button.extend({
      defaultProps: {
        variant: 'light',
        loaderProps: { type: 'dots' },
        style: { backdropFilter: 'blur(4px)' },
      },
    }),
    Alert: Select.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Card: Select.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Menu: Menu.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Paper: Select.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Select: Select.extend({
      defaultProps: {
        comboboxProps: { radius: 'lg' },
      },
    }),
    Skeleton: Skeleton.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Accordion: Accordion.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
    Combobox: Combobox.extend({
      defaultProps: {
        radius: 'lg',
      },
    }),
  },
});

type Props = {
  children: ReactNode;
};

export function ThemeProvider({ children }: Props) {
  return (
    <MantineProvider forceColorScheme="light" defaultColorScheme="light" theme={theme}>
      {children}
    </MantineProvider>
  );
}

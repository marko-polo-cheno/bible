export const styles = {
  container: {
    padding: '20px'
  },
  flexContainer: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: '8px',
    alignItems: 'flex-start'
  },
  radioRoot: {
    display: 'inline-flex',
    alignItems: 'center',
    cursor: 'pointer'
  },
  radioInner: {
    display: 'none'
  },
  autocomp: {
    dropdown: {
      backgroundColor: '#f8f9fa', // Light gray background
      borderRadius: '8px', // Rounded corners
      boxShadow: '0px 4px 10px rgba(0, 0, 0, 0.1)', // Subtle shadow for depth
    },
    item: {
      padding: '10px 12px', // Add padding for better spacing
      fontSize: '14px', // Adjust font size

      // Hover state styles (targeting hovered items)
      '&.mantine-Autocomplete-option[data-hovered]': {
        backgroundColor: '#1c7ed6', // Blue background on hover
        color: 'white', // White text when hovered
      },

      // Selected state styles (targeting selected items)
      '&.mantine-Autocomplete-option[data-selected]': {
        backgroundColor: '#1864ab', // Darker blue when selected
        color: 'white', // White text for selected item
      },

      // Add a smooth transition for hover and selection effects
      transition: 'background-color 0.2s ease, color 0.2s ease',
    },
    input: {
      border: '1px solid #ced4da', // Custom input border
      borderRadius: '6px', // Rounded input corners
      padding: '10px 12px', // Spacing inside the input
      fontSize: '14px', // Adjust font size
    }},
    getRadioLabel: (isSelected: boolean) => ({
      backgroundColor: isSelected ? '#d3d3d3' : '#f5f5f5',
      padding: '8px 12px',
      borderRadius: '4px',
      border: `1px solid ${isSelected ? '#888' : '#ccc'}`,
      cursor: 'pointer',
      transition: 'background-color 0.2s ease, border-color 0.2s ease',
      display: 'inline-block',
      whiteSpace: 'nowrap' as const
    }),
    verseDisplay: {
      whiteSpace: 'pre-wrap' as const,
      lineHeight: 1.0
    }
  };

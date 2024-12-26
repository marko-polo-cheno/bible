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
      lineHeight: 1.5
    }
  };

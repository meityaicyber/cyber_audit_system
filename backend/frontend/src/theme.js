import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00D4FF',
      light: '#33DDFF',
      dark: '#0099CC',
      contrastText: '#0A0E17',
    },
    secondary: {
      main: '#00E676',
      light: '#33EB91',
      dark: '#00B85C',
      contrastText: '#0A0E17',
    },
    error: {
      main: '#FF1744',
      light: '#FF4569',
      dark: '#CC1236',
    },
    warning: {
      main: '#FF9100',
      light: '#FFA733',
      dark: '#CC7400',
    },
    info: {
      main: '#7C4DFF',
      light: '#9670FF',
      dark: '#633ECC',
    },
    success: {
      main: '#00E676',
      light: '#33EB91',
      dark: '#00B85C',
    },
    background: {
      default: '#0A0E17',
      paper: '#111827',
    },
    text: {
      primary: '#E2E8F0',
      secondary: '#94A3B8',
    },
    divider: 'rgba(255, 255, 255, 0.06)',
  },
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
    h1: { fontWeight: 800, letterSpacing: '-0.02em' },
    h2: { fontWeight: 700, letterSpacing: '-0.01em' },
    h3: { fontWeight: 700 },
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    button: { fontWeight: 600, letterSpacing: '0.02em' },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundImage: 'radial-gradient(ellipse at 50% 0%, rgba(0, 212, 255, 0.04) 0%, transparent 60%)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: 'rgba(10, 14, 23, 0.65)',
          backdropFilter: 'blur(25px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: 'rgba(10, 14, 23, 0.5)',
          backdropFilter: 'blur(25px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4)',
          transition: 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
          '&:hover': {
            border: '1px solid rgba(0, 212, 255, 0.3)',
            boxShadow: '0 8px 40px rgba(0, 212, 255, 0.15), inset 0 0 20px rgba(0, 212, 255, 0.05)',
            transform: 'translateY(-4px)',
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none',
          fontWeight: 600,
          padding: '8px 20px',
          transition: 'all 0.3s ease',
        },
        containedPrimary: {
          background: 'linear-gradient(135deg, #00D4FF 0%, #0099CC 100%)',
          boxShadow: '0 4px 15px rgba(0, 212, 255, 0.3)',
          '&:hover': {
            background: 'linear-gradient(135deg, #33DDFF 0%, #00B8E6 100%)',
            boxShadow: '0 6px 20px rgba(0, 212, 255, 0.5), inset 0 0 10px rgba(255,255,255,0.2)',
            transform: 'translateY(-1px)',
          },
        },
        outlinedPrimary: {
          borderColor: 'rgba(0, 212, 255, 0.5)',
          '&:hover': {
            backgroundColor: 'rgba(0, 212, 255, 0.1)',
            borderColor: '#00D4FF',
            boxShadow: '0 0 15px rgba(0, 212, 255, 0.3)',
          }
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            '& fieldset': {
              borderColor: 'rgba(255, 255, 255, 0.1)',
            },
            '&:hover fieldset': {
              borderColor: 'rgba(0, 212, 255, 0.3)',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#00D4FF',
              boxShadow: '0 0 10px rgba(0, 212, 255, 0.15)',
            },
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.2s ease',
          '&:hover': {
            backgroundColor: 'rgba(0, 212, 255, 0.04) !important',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: 'rgba(255, 255, 255, 0.04)',
          transition: 'all 0.2s ease',
        },
        head: {
          fontWeight: 600,
          color: '#E2E8F0',
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          fontSize: '0.75rem',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: 'rgba(10, 14, 23, 0.95)',
          backdropFilter: 'blur(20px)',
          borderRight: '1px solid rgba(255, 255, 255, 0.06)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(10, 14, 23, 0.85)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          boxShadow: 'none',
        },
      },
    },
  },
});

export default theme;

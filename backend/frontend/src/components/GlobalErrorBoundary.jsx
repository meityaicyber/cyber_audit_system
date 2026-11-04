import React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import { ErrorOutline, Refresh } from '@mui/icons-material';

function GlobalErrorBoundary({ error, resetErrorBoundary }) {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0A0E17',
        p: 2,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          maxWidth: 500,
          p: 4,
          borderRadius: 3,
          textAlign: 'center',
          background: 'rgba(255, 23, 68, 0.05)',
          border: '1px solid rgba(255, 23, 68, 0.2)',
        }}
      >
        <ErrorOutline sx={{ fontSize: 64, color: '#FF1744', mb: 2 }} />
        <Typography variant="h5" fontWeight={700} sx={{ mb: 1, color: '#E2E8F0' }}>
          Oops! Something went wrong.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
          {error?.message || 'An unexpected error occurred in the application.'}
        </Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<Refresh />}
          onClick={() => {
            if (resetErrorBoundary) {
              resetErrorBoundary();
            } else {
              window.location.reload();
            }
          }}
        >
          Reload Page
        </Button>
      </Paper>
    </Box>
  );
}

export default GlobalErrorBoundary;

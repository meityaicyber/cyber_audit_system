import React from 'react';
import { Box, Typography } from '@mui/material';
import { Block } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

function RoleGuard({ roles, children }) {
  const { user } = useAuth();
  const hasRequiredRole = user?.roles?.some((r) => roles.includes(r));

  if (!hasRequiredRole) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '60vh',
          gap: 2,
        }}
      >
        <Block sx={{ fontSize: 80, color: 'error.main', opacity: 0.6 }} />
        <Typography variant="h4" color="error.main" fontWeight={700}>
          Access Denied
        </Typography>
        <Typography variant="body1" color="text.secondary">
          You do not have permission to access this page.
        </Typography>
      </Box>
    );
  }

  return children;
}

export default RoleGuard;

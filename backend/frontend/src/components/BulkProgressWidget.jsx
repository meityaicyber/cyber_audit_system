import React from 'react';
import { Box, Paper, Typography, LinearProgress, IconButton, Collapse } from '@mui/material';
import { Close, Minimize, OpenInFull, CheckCircle } from '@mui/icons-material';
import { useBulkUpload } from '../contexts/BulkUploadContext';

const BulkProgressWidget = () => {
  const {
    bulkProgress, bulkTotal, bulkRunning, bulkFinished,
    isWidgetOpen, isWidgetMinimized, closeWidget, toggleMinimize
  } = useBulkUpload();

  if (!isWidgetOpen) return null;

  return (
    <Paper
      elevation={6}
      sx={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        width: 350,
        zIndex: 9999,
        background: 'rgba(10, 14, 23, 0.95)',
        border: '1px solid rgba(0, 212, 255, 0.3)',
        borderRadius: 2,
        overflow: 'hidden',
        backdropFilter: 'blur(10px)',
      }}
    >
      {/* Header */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 2,
        py: 1,
        background: 'rgba(0, 212, 255, 0.1)',
        borderBottom: '1px solid rgba(0, 212, 255, 0.2)'
      }}>
        <Typography variant="subtitle2" fontWeight={600} color="text.primary">
          Bulk Processing {bulkRunning ? 'Running' : bulkFinished ? 'Completed' : ''}
        </Typography>
        <Box>
          <IconButton size="small" onClick={toggleMinimize} sx={{ color: 'text.secondary' }}>
            {isWidgetMinimized ? <OpenInFull fontSize="small" /> : <Minimize fontSize="small" sx={{ mb: 1 }} />}
          </IconButton>
          {!bulkRunning && (
            <IconButton size="small" onClick={closeWidget} sx={{ color: 'text.secondary' }}>
              <Close fontSize="small" />
            </IconButton>
          )}
        </Box>
      </Box>

      {/* Body */}
      <Collapse in={!isWidgetMinimized}>
        <Box sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Processed {bulkProgress} of {bulkTotal} files
            </Typography>
            {bulkFinished && <CheckCircle color="success" fontSize="small" />}
          </Box>
          <LinearProgress
            variant="determinate"
            value={bulkTotal > 0 ? (bulkProgress / bulkTotal) * 100 : 0}
            sx={{
              height: 8,
              borderRadius: 4,
              backgroundColor: 'rgba(0, 212, 255, 0.1)',
              '& .MuiLinearProgress-bar': { background: 'linear-gradient(90deg, #00D4FF, #00E676)' }
            }}
          />
        </Box>
      </Collapse>
    </Paper>
  );
};

export default BulkProgressWidget;

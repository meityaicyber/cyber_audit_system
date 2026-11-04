import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { Security } from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';

const actionColors = {
  FILE_UPLOAD: 'primary',
  FILE_DELETE: 'error',
  USER_LOGIN: 'success',
  USER_CREATE: 'info',
};

function AuditLogsPage() {
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 25 });
  const [actionFilter, setActionFilter] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', paginationModel.page, paginationModel.pageSize, actionFilter],
    queryFn: async () => {
      const params = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
      };
      if (actionFilter) params.action = actionFilter;
      const response = await api.get('/api/audit-logs', { params });
      return response.data;
    },
    keepPreviousData: true,
  });

  const logs = data?.logs || [];
  const total = data?.total || 0;

  const columns = [
    {
      field: 'action',
      headerName: 'Action',
      width: 150,
      renderCell: (params) => (
        <Chip
          label={params.value}
          color={actionColors[params.value] || 'default'}
          size="small"
          sx={{ fontWeight: 600, fontSize: '0.7rem' }}
        />
      ),
    },
    {
      field: 'username',
      headerName: 'User',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2" fontWeight={500}>
          {params.value || '—'}
        </Typography>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          color={params.value === 'SUCCESS' ? 'success' : 'error'}
          variant="outlined"
          size="small"
          sx={{ fontWeight: 600, fontSize: '0.7rem' }}
        />
      ),
    },
    {
      field: 'details',
      headerName: 'Details',
      flex: 1,
      renderCell: (params) => (
        <Typography
          variant="body2"
          color="text.secondary"
          noWrap
          sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
        >
          {params.value ? JSON.stringify(params.value).substring(0, 80) : '—'}
        </Typography>
      ),
    },
    {
      field: 'created_at',
      headerName: 'Timestamp',
      width: 200,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {new Date(params.value).toLocaleString()}
        </Typography>
      ),
    },
  ];

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ mb: 0.5, background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Audit Logs
          </Typography>
          <Typography variant="body2" color="text.secondary">
            System activity and security event tracking
          </Typography>
        </Box>
      </Box>

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Action Filter</InputLabel>
          <Select
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPaginationModel((prev) => ({ ...prev, page: 0 }));
            }}
            label="Action Filter"
          >
            <MenuItem value="">All Actions</MenuItem>
            <MenuItem value="FILE_UPLOAD">File Upload</MenuItem>
            <MenuItem value="FILE_DELETE">File Delete</MenuItem>
            <MenuItem value="USER_LOGIN">User Login</MenuItem>
            <MenuItem value="USER_CREATE">User Create</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <Card className="fade-in-up" sx={{ flexGrow: 1 }}>
        <CardContent sx={{ p: 0 }}>
          <Box sx={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={logs}
            columns={columns}
            getRowId={(row) => row.log_id}
            rowCount={total}
            loading={isLoading}
            paginationMode="server"
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            pageSizeOptions={[10, 25, 50]}
            disableRowSelectionOnClick
            sx={{
              border: 'none',
              '& .MuiDataGrid-cell': {
                borderBottom: '1px solid rgba(255,255,255,0.04)',
              },
              '& .MuiDataGrid-columnHeaders': {
                backgroundColor: 'rgba(0, 0, 0, 0.4)',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
                color: '#E2E8F0',
              },
              '& .MuiDataGrid-footerContainer': {
                borderTop: '1px solid rgba(255,255,255,0.08)',
              },
            }}
            slots={{
              noRowsOverlay: () => (
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <Security sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                  <Typography color="text.secondary">No audit logs found</Typography>
                </Box>
              ),
            }}
          />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

export default AuditLogsPage;

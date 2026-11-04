import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tooltip,
} from '@mui/material';
import { Add, Edit, Delete, Person } from '@mui/icons-material';
import { useForm, Controller } from 'react-hook-form';
import { useSnackbar } from 'notistack';
import { DataGrid } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/axios';

const ROLES = ['ADMIN', 'AUDITOR', 'REVIEWER'];

function UserManagementPage() {
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editUser, setEditUser] = useState(null);

  const { control, register, handleSubmit, reset, formState: { errors } } = useForm();

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const response = await api.get('/api/users', { params: { limit: 100 } });
      return response.data.users;
    },
  });

  const mutation = useMutation({
    mutationFn: async (data) => {
      if (editUser) {
        return api.put(`/api/users/${editUser.user_id}`, {
          email: data.email,
          full_name: data.full_name || null,
          roles: data.roles,
        });
      } else {
        return api.post('/api/users', {
          username: data.username,
          email: data.email,
          password: data.password,
          full_name: data.full_name || null,
          roles: data.roles,
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      enqueueSnackbar(`User ${editUser ? 'updated' : 'created'} successfully`, { variant: 'success' });
      setDialogOpen(false);
    },
    onError: (err) => {
      enqueueSnackbar(err.response?.data?.detail || 'Operation failed', { variant: 'error' });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (userId) => api.delete(`/api/users/${userId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      enqueueSnackbar('User deactivated', { variant: 'success' });
    },
    onError: (err) => {
      enqueueSnackbar(err.response?.data?.detail || 'Delete failed', { variant: 'error' });
    }
  });

  const handleOpenCreate = () => {
    setEditUser(null);
    reset({ username: '', email: '', password: '', full_name: '', roles: ['AUDITOR'] });
    setDialogOpen(true);
  };

  const handleOpenEdit = (user) => {
    setEditUser(user);
    reset({
      username: user.username,
      email: user.email,
      password: '',
      full_name: user.full_name || '',
      roles: user.roles,
    });
    setDialogOpen(true);
  };

  const onSubmit = (data) => {
    mutation.mutate(data);
  };

  const handleDelete = (userId) => {
    if (window.confirm('Are you sure you want to deactivate this user?')) {
      deleteMutation.mutate(userId);
    }
  };

  const columns = [
    {
      field: 'username',
      headerName: 'User',
      flex: 1,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, height: '100%' }}>
          <Person sx={{ color: 'text.secondary' }} />
          <Box sx={{ lineHeight: 1.2 }}>
            <Typography variant="body2" fontWeight={600}>
              {params.value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {params.row.full_name || '—'}
            </Typography>
          </Box>
        </Box>
      )
    },
    {
      field: 'email',
      headerName: 'Email',
      flex: 1,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          {params.value}
        </Typography>
      )
    },
    {
      field: 'roles',
      headerName: 'Roles',
      flex: 1,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center', height: '100%' }}>
          {params.value.map((r) => (
            <Chip
              key={r}
              label={r}
              size="small"
              color={r === 'ADMIN' ? 'error' : r === 'AUDITOR' ? 'primary' : 'default'}
              sx={{ fontWeight: 600, fontSize: '0.65rem' }}
            />
          ))}
        </Box>
      )
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          <Chip
            label={params.value ? 'Active' : 'Inactive'}
            color={params.value ? 'success' : 'default'}
            size="small"
            sx={{ fontWeight: 600 }}
          />
        </Box>
      )
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          {new Date(params.value).toLocaleDateString()}
        </Typography>
      )
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', height: '100%', width: '100%' }}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => handleOpenEdit(params.row)} sx={{ color: '#00D4FF' }}>
              <Edit fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Deactivate">
            <IconButton size="small" onClick={() => handleDelete(params.row.user_id)} sx={{ color: '#FF1744' }}>
              <Delete fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      )
    }
  ];

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ mb: 0.5 , background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>
            User Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage system users and their roles
          </Typography>
        </Box>
        <Button
          id="btn-create-user"
          variant="contained"
          startIcon={<Add />}
          onClick={handleOpenCreate}
        >
          Add User
        </Button>
      </Box>

      <Card className="fade-in-up" sx={{ flexGrow: 1 }}>
        <CardContent sx={{ p: 0 }}>
          <Box sx={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={users}
            columns={columns}
            getRowId={(row) => row.user_id}
            loading={isLoading}
            disableRowSelectionOnClick
            initialState={{
              pagination: { paginationModel: { pageSize: 10 } },
            }}
            pageSizeOptions={[10, 25, 50]}
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
          />
          </Box>
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            background: 'rgba(17, 24, 39, 0.95)',
            backdropFilter: 'blur(20px)',
            borderRadius: 3,
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          {editUser ? 'Edit User' : 'Create User'}
        </DialogTitle>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            {!editUser && (
              <TextField
                label="Username"
                fullWidth
                {...register('username', { required: 'Required', minLength: { value: 3, message: 'Min 3 chars' } })}
                error={!!errors.username}
                helperText={errors.username?.message}
              />
            )}
            <TextField
              label="Email"
              fullWidth
              type="email"
              {...register('email', { required: 'Required' })}
              error={!!errors.email}
              helperText={errors.email?.message}
            />
            {!editUser && (
              <TextField
                label="Password"
                fullWidth
                type="password"
                {...register('password', { required: 'Required', minLength: { value: 8, message: 'Min 8 chars' } })}
                error={!!errors.password}
                helperText={errors.password?.message}
              />
            )}
            <TextField
              label="Full Name"
              fullWidth
              {...register('full_name')}
            />
            <Controller
              name="roles"
              control={control}
              rules={{ required: 'Select at least one role' }}
              render={({ field }) => (
                <FormControl fullWidth error={!!errors.roles}>
                  <InputLabel>Roles</InputLabel>
                  <Select
                    {...field}
                    multiple
                    label="Roles"
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {selected.map((v) => (
                          <Chip key={v} label={v} size="small" />
                        ))}
                      </Box>
                    )}
                  >
                    {ROLES.map((role) => (
                      <MenuItem key={role} value={role}>
                        {role}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            />
          </DialogContent>
          <DialogActions sx={{ p: 3, pt: 1 }}>
            <Button onClick={() => setDialogOpen(false)} color="inherit" disabled={mutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="contained" disabled={mutation.isPending}>
              {editUser ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  );
}

export default UserManagementPage;

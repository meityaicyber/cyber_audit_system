import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Avatar,
  Grid,
  Chip,
  Divider,
  Alert,
} from '@mui/material';
import { Person, Email, Badge, CalendarToday, Save } from '@mui/icons-material';
import { useForm } from 'react-hook-form';
import { useSnackbar } from 'notistack';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/axios';

function ProfilePage() {
  const { user, fetchMe } = useAuth();
  const { enqueueSnackbar } = useSnackbar();
  const [saving, setSaving] = useState(false);

  const { register, handleSubmit } = useForm({
    defaultValues: {
      full_name: user?.full_name || '',
      email: user?.email || '',
    },
  });

  const onSubmit = async (data) => {
    setSaving(true);
    try {
      await api.put('/api/users/me', {
        full_name: data.full_name || null,
        email: data.email,
      });
      await fetchMe();
      enqueueSnackbar('Profile updated successfully', { variant: 'success' });
    } catch (err) {
      enqueueSnackbar(err.response?.data?.detail || 'Update failed', { variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" fontWeight={800} sx={{ mb: 1 , background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>
        Profile
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        View and manage your account information
      </Typography>

      <Grid container spacing={3}>
        {/* Profile Card */}
        <Grid item xs={12} md={4}>
          <Card className="fade-in-up">
            <CardContent sx={{ p: 4, textAlign: 'center' }}>
              <Avatar
                sx={{
                  width: 96,
                  height: 96,
                  mx: 'auto',
                  mb: 2,
                  background: 'linear-gradient(135deg, #00D4FF, #7C4DFF)',
                  fontSize: '2.5rem',
                  fontWeight: 800,
                }}
              >
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </Avatar>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
                {user?.full_name || user?.username}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                @{user?.username}
              </Typography>

              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
                {user?.roles?.map((role) => (
                  <Chip
                    key={role}
                    label={role}
                    color={role === 'ADMIN' ? 'error' : role === 'AUDITOR' ? 'primary' : 'default'}
                    sx={{ fontWeight: 600 }}
                  />
                ))}
              </Box>

              <Divider sx={{ my: 3 }} />

              <Box sx={{ textAlign: 'left' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                  <Email sx={{ color: 'text.secondary', fontSize: 20 }} />
                  <Box>
                    <Typography variant="caption" color="text.secondary">Email</Typography>
                    <Typography variant="body2" fontWeight={500}>{user?.email}</Typography>
                  </Box>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                  <CalendarToday sx={{ color: 'text.secondary', fontSize: 20 }} />
                  <Box>
                    <Typography variant="caption" color="text.secondary">Member Since</Typography>
                    <Typography variant="body2" fontWeight={500}>
                      {user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                    </Typography>
                  </Box>
                </Box>
                {user?.last_login && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Badge sx={{ color: 'text.secondary', fontSize: 20 }} />
                    <Box>
                      <Typography variant="caption" color="text.secondary">Last Login</Typography>
                      <Typography variant="body2" fontWeight={500}>
                        {new Date(user.last_login).toLocaleString()}
                      </Typography>
                    </Box>
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Edit Form */}
        <Grid item xs={12} md={8}>
          <Card className="fade-in-up" sx={{ animationDelay: '100ms' }}>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" fontWeight={700} sx={{ mb: 3 }}>
                Edit Profile
              </Typography>

              <form onSubmit={handleSubmit(onSubmit)}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <TextField
                    label="Username"
                    value={user?.username || ''}
                    disabled
                    fullWidth
                    helperText="Username cannot be changed"
                  />
                  <TextField
                    label="Full Name"
                    fullWidth
                    {...register('full_name')}
                  />
                  <TextField
                    label="Email"
                    fullWidth
                    type="email"
                    {...register('email', { required: 'Email is required' })}
                  />

                  <Button
                    type="submit"
                    variant="contained"
                    startIcon={<Save />}
                    disabled={saving}
                    sx={{ alignSelf: 'flex-start', mt: 1 }}
                  >
                    {saving ? 'Saving...' : 'Save Changes'}
                  </Button>
                </Box>
              </form>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default ProfilePage;

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Grid,
  MenuItem,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { Add, Edit, Delete, Visibility } from '@mui/icons-material';
import { useSnackbar } from 'notistack';
import api from '../api/axios';

const agencyTypes = [
  'CERT_IN_EMPANELLED',
  'PRIVATE_AUDITOR',
  'INTERNAL_AUDIT_TEAM',
  'GOVERNMENT_AGENCY',
  'THIRD_PARTY_ASSESSOR',
];

const statuses = ['ACTIVE', 'INACTIVE', 'SUSPENDED', 'BLACKLISTED'];

export default function AgencyManagementPage() {
  const [agencies, setAgencies] = useState([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingAgency, setEditingAgency] = useState(null);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [selectedViewAgency, setSelectedViewAgency] = useState(null);
  const [agencyStats, setAgencyStats] = useState(null);
  const { enqueueSnackbar } = useSnackbar();

  const [formData, setFormData] = useState({
    agency_code: '',
    agency_name: '',
    agency_type: 'PRIVATE_AUDITOR',
    registration_number: '',
    cert_in_empanelled: false,
    empanelment_number: '',
    empanelment_expiry: '',
    contact_person: '',
    contact_email: '',
    contact_phone: '',
    website: '',
    address: '',
    city: '',
    state: '',
    country: 'India',
    pincode: '',
    status: 'ACTIVE',
    remarks: '',
  });

  useEffect(() => {
    fetchAgencies();
  }, []);

  const fetchAgencies = async () => {
    try {
      const response = await api.get('/api/agencies', { params: { limit: 100 } });
      setAgencies(response.data.agencies || []);
    } catch (err) {
      enqueueSnackbar('Failed to load agencies', { variant: 'error' });
    }
  };

  const handleOpenDialog = (agency = null) => {
    if (agency) {
      setEditingAgency(agency);
      setFormData({
        agency_code: agency.agency_code || '',
        agency_name: agency.agency_name || '',
        agency_type: agency.agency_type || 'PRIVATE_AUDITOR',
        registration_number: agency.registration_number || '',
        cert_in_empanelled: agency.cert_in_empanelled || false,
        empanelment_number: agency.empanelment_number || '',
        empanelment_expiry: agency.empanelment_expiry ? agency.empanelment_expiry.split('T')[0] : '',
        contact_person: agency.contact_person || '',
        contact_email: agency.contact_email || '',
        contact_phone: agency.contact_phone || '',
        website: agency.website || '',
        address: agency.address || '',
        city: agency.city || '',
        state: agency.state || '',
        country: agency.country || 'India',
        pincode: agency.pincode || '',
        status: agency.status || 'ACTIVE',
        remarks: agency.remarks || '',
      });
    } else {
      setEditingAgency(null);
      setFormData({
        agency_code: '',
        agency_name: '',
        agency_type: 'PRIVATE_AUDITOR',
        registration_number: '',
        cert_in_empanelled: false,
        empanelment_number: '',
        empanelment_expiry: '',
        contact_person: '',
        contact_email: '',
        contact_phone: '',
        website: '',
        address: '',
        city: '',
        state: '',
        country: 'India',
        pincode: '',
        status: 'ACTIVE',
        remarks: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
  };

  const handleOpenViewDialog = async (agency) => {
    setSelectedViewAgency(agency);
    setAgencyStats(null);
    setViewDialogOpen(true);
    try {
      const res = await api.get(`/api/agencies/${agency.agency_id}/stats`);
      setAgencyStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats', err);
    }
  };

  const handleCloseViewDialog = () => {
    setViewDialogOpen(false);
    setSelectedViewAgency(null);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async () => {
    try {
      const payload = { ...formData };
      if (!payload.empanelment_expiry) payload.empanelment_expiry = null;

      if (editingAgency) {
        await api.put(`/api/agencies/${editingAgency.agency_id}`, payload);
        enqueueSnackbar('Agency updated', { variant: 'success' });
      } else {
        await api.post('/api/agencies', payload);
        enqueueSnackbar('Agency created', { variant: 'success' });
      }
      handleCloseDialog();
      fetchAgencies();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to save agency';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this agency?')) return;
    try {
      await api.delete(`/api/agencies/${id}`);
      enqueueSnackbar('Agency deleted', { variant: 'success' });
      fetchAgencies();
    } catch (err) {
      enqueueSnackbar('Failed to delete agency', { variant: 'error' });
    }
  };

  return (
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
        <Typography variant="h4" fontWeight="bold" sx={{ background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Agency Management
        </Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
          Add Agency
        </Button>
      </Box>

      <TableContainer component={Paper} elevation={3}>
        <Table>
          <TableHead sx={{ backgroundColor: 'background.default' }}>
            <TableRow>
              <TableCell>Code</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Contact</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {agencies.map((agency) => (
              <TableRow key={agency.agency_id}>
                <TableCell>{agency.agency_code}</TableCell>
                <TableCell>{agency.agency_name}</TableCell>
                <TableCell>{agency.agency_type}</TableCell>
                <TableCell>{agency.status}</TableCell>
                <TableCell>{agency.contact_person}</TableCell>
                <TableCell>
                  <IconButton color="info" onClick={() => handleOpenViewDialog(agency)}>
                    <Visibility />
                  </IconButton>
                  <IconButton color="primary" onClick={() => handleOpenDialog(agency)}>
                    <Edit />
                  </IconButton>
                  <IconButton color="error" onClick={() => handleDelete(agency.agency_id)}>
                    <Delete />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
            {agencies.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 3 }}>
                  No agencies found. Click "Add Agency" to create one.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>{editingAgency ? 'Edit Agency' : 'Add New Agency'}</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={3}>
            {/* Basic Info */}
            <Grid item xs={12}>
              <Typography variant="h6" color="primary">Basic Information</Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Agency Code *" name="agency_code" value={formData.agency_code} onChange={handleChange} disabled={!!editingAgency} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Agency Name *" name="agency_name" value={formData.agency_name} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField select fullWidth label="Agency Type *" name="agency_type" value={formData.agency_type} onChange={handleChange}>
                {agencyTypes.map(type => <MenuItem key={type} value={type}>{type}</MenuItem>)}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Registration Number" name="registration_number" value={formData.registration_number} onChange={handleChange} />
            </Grid>
            
            {/* Empanelment */}
            <Grid item xs={12}>
              <Typography variant="h6" color="primary" sx={{ mt: 2 }}>Empanelment Details</Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControlLabel control={<Checkbox checked={formData.cert_in_empanelled} onChange={handleChange} name="cert_in_empanelled" />} label="CERT-In Empanelled" />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Empanelment Number" name="empanelment_number" value={formData.empanelment_number} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth type="date" label="Empanelment Expiry" name="empanelment_expiry" value={formData.empanelment_expiry} onChange={handleChange} InputLabelProps={{ shrink: true }} />
            </Grid>

            {/* Contact Details */}
            <Grid item xs={12}>
              <Typography variant="h6" color="primary" sx={{ mt: 2 }}>Contact Details</Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Contact Person *" name="contact_person" value={formData.contact_person} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth type="email" label="Contact Email *" name="contact_email" value={formData.contact_email} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Contact Phone" name="contact_phone" value={formData.contact_phone} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Website" name="website" value={formData.website} onChange={handleChange} />
            </Grid>

            {/* Address */}
            <Grid item xs={12}>
              <Typography variant="h6" color="primary" sx={{ mt: 2 }}>Address</Typography>
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth multiline rows={2} label="Address" name="address" value={formData.address} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="City" name="city" value={formData.city} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="State" name="state" value={formData.state} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Country" name="country" value={formData.country} onChange={handleChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Pincode" name="pincode" value={formData.pincode} onChange={handleChange} />
            </Grid>

            {/* Other */}
            <Grid item xs={12}>
              <Typography variant="h6" color="primary" sx={{ mt: 2 }}>Other Info</Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField select fullWidth label="Status *" name="status" value={formData.status} onChange={handleChange}>
                {statuses.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth multiline rows={2} label="Remarks" name="remarks" value={formData.remarks} onChange={handleChange} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={handleCloseDialog} color="inherit">Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">
            {editingAgency ? 'Save Changes' : 'Create Agency'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* View Details Dialog */}
      <Dialog open={viewDialogOpen} onClose={handleCloseViewDialog} maxWidth="md" fullWidth>
        {selectedViewAgency && (
          <>
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="h6">Agency Details</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">Total Reports:</Typography>
                <Typography variant="h6" color="primary" fontWeight="bold">
                  {agencyStats ? agencyStats.total_reports : '...'}
                </Typography>
              </Box>
            </DialogTitle>
            <DialogContent dividers>
              <Grid container spacing={3}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Code</Typography>
                  <Typography variant="body1">{selectedViewAgency.agency_code}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Name</Typography>
                  <Typography variant="body1">{selectedViewAgency.agency_name}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Type</Typography>
                  <Typography variant="body1">{selectedViewAgency.agency_type}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Status</Typography>
                  <Typography variant="body1">{selectedViewAgency.status}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Registration Number</Typography>
                  <Typography variant="body1">{selectedViewAgency.registration_number || '—'}</Typography>
                </Grid>
                
                <Grid item xs={12}>
                  <Typography variant="h6" color="primary" sx={{ mt: 2 }}>Empanelment Details</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">CERT-In Empanelled</Typography>
                  <Typography variant="body1">{selectedViewAgency.cert_in_empanelled ? 'Yes' : 'No'}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Empanelment Number</Typography>
                  <Typography variant="body1">{selectedViewAgency.empanelment_number || '—'}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Empanelment Expiry</Typography>
                  <Typography variant="body1">{selectedViewAgency.empanelment_expiry ? new Date(selectedViewAgency.empanelment_expiry).toLocaleDateString() : '—'}</Typography>
                </Grid>

                <Grid item xs={12}>
                  <Typography variant="h6" color="primary" sx={{ mt: 2 }}>Contact & Address</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Contact Person</Typography>
                  <Typography variant="body1">{selectedViewAgency.contact_person}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Contact Email</Typography>
                  <Typography variant="body1">{selectedViewAgency.contact_email}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Contact Phone</Typography>
                  <Typography variant="body1">{selectedViewAgency.contact_phone || '—'}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Website</Typography>
                  <Typography variant="body1">{selectedViewAgency.website || '—'}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle2" color="text.secondary">Address</Typography>
                  <Typography variant="body1">
                    {selectedViewAgency.address ? `${selectedViewAgency.address}, ` : ''}
                    {selectedViewAgency.city ? `${selectedViewAgency.city}, ` : ''}
                    {selectedViewAgency.state ? `${selectedViewAgency.state}, ` : ''}
                    {selectedViewAgency.country} {selectedViewAgency.pincode}
                  </Typography>
                </Grid>

                <Grid item xs={12}>
                  <Typography variant="subtitle2" color="text.secondary">Remarks</Typography>
                  <Typography variant="body1">{selectedViewAgency.remarks || '—'}</Typography>
                </Grid>
              </Grid>
            </DialogContent>
            <DialogActions sx={{ px: 3, py: 2 }}>
              <Button onClick={handleCloseViewDialog} variant="contained" color="primary">Close</Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
}

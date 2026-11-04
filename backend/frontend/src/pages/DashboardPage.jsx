import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Skeleton,
  Button,
  Paper,
  Divider,
  IconButton
} from '@mui/material';
import {
  Description,
  People,
  CheckCircle,
  Warning,
  CloudUpload,
  PictureAsPdf,
  Article,
  InsertDriveFile,
  ArrowForward,
  Business
} from '@mui/icons-material';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, Legend } from 'recharts';
import api from '../api/axios';

const muiStatusColor = {
  UPLOADED: 'info',
  VALIDATED: 'success',
  REJECTED: 'error',
  QUARANTINED: 'warning',
  PIPELINE_RUNNING: 'secondary',
  FAILED: 'error',
};

const rechartsColors = {
  VALIDATED: '#00E676',
  REJECTED: '#FF1744',
  UPLOADED: '#00D4FF',
  QUARANTINED: '#FFEA00',
  PIPELINE_RUNNING: '#7C4DFF',
};

function StatCard({ title, value, icon, color, delay }) {
  return (
    <Card
      className="fade-in-up"
      sx={{
        animationDelay: `${delay}ms`,
        position: 'relative',
        overflow: 'hidden',
        height: '100%',
        boxShadow: '0 4px 20px 0 rgba(0,0,0,0.2)',
      }}
    >
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {title}
            </Typography>
            <Typography variant="h3" fontWeight={800} sx={{ color }}>
              {value}
            </Typography>
          </Box>
          <Box
            sx={{
              p: 1.5,
              borderRadius: 2,
              background: `${color}15`,
              display: 'flex',
              boxShadow: `0 0 15px ${color}20`
            }}
          >
            {React.cloneElement(icon, { sx: { fontSize: 32, color } })}
          </Box>
        </Box>
      </CardContent>
      <Box
        sx={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: 4,
          background: `linear-gradient(90deg, ${color}, transparent)`,
        }}
      />
    </Card>
  );
}

const getFileIcon = (filename) => {
  const ext = filename?.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return <PictureAsPdf sx={{ color: '#FF1744' }} />;
  if (ext === 'docx' || ext === 'doc') return <Article sx={{ color: '#2962FF' }} />;
  return <InsertDriveFile sx={{ color: '#9E9E9E' }} />;
};

function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await api.get('/api/dashboard/stats');
        setStats(response.data);
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <Box>
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {[1, 2, 3, 4].map((i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Skeleton variant="rounded" height={130} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
        <Grid container spacing={3} sx={{ mb: 4 }}>
           <Grid item xs={12} md={8}>
             <Skeleton variant="rounded" height={350} sx={{ borderRadius: 3 }} />
           </Grid>
           <Grid item xs={12} md={4}>
             <Skeleton variant="rounded" height={350} sx={{ borderRadius: 3 }} />
           </Grid>
        </Grid>
      </Box>
    );
  }

  const validatedCount = stats?.reports_by_status?.VALIDATED || 0;
  const rejectedCount = stats?.reports_by_status?.REJECTED || 0;
  
  // Prepare pie chart data
  const pieData = Object.keys(stats?.reports_by_status || {}).map(key => ({
    name: key,
    value: stats.reports_by_status[key],
    color: rechartsColors[key] || '#9E9E9E'
  })).filter(item => item.value > 0);

  return (
    <Box>
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ mb: 1, background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Dashboard Overview
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Real-time insights and statistics of your cybersecurity audit reports
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<CloudUpload />} onClick={() => navigate('/upload')} sx={{ borderRadius: 2, px: 3, py: 1, background: 'linear-gradient(45deg, #00D4FF, #2962FF)' }}>
          Upload New Report
        </Button>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Reports"
            value={stats?.total_reports || 0}
            icon={<Description />}
            color="#00D4FF"
            delay={0}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Users"
            value={stats?.total_users || 0}
            icon={<People />}
            color="#7C4DFF"
            delay={100}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Validated Reports"
            value={validatedCount}
            icon={<CheckCircle />}
            color="#00E676"
            delay={200}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Rejected Reports"
            value={rejectedCount}
            icon={<Warning />}
            color="#FF1744"
            delay={300}
          />
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Chart Section */}
        <Grid item xs={12} md={7} lg={8}>
          <Card className="fade-in-up" sx={{ animationDelay: '400ms', height: '100%', boxShadow: '0 4px 20px 0 rgba(0,0,0,0.2)' }}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
                Report Processing Status
              </Typography>
              <Divider sx={{ mb: 3 }} />
              <Box sx={{ height: 300, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={80}
                        outerRadius={110}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip 
                        contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', borderRadius: '8px', border: 'none', color: '#fff', boxShadow: '0 4px 20px 0 rgba(0,0,0,0.5)' }}
                        itemStyle={{ color: '#fff' }}
                      />
                      <Legend verticalAlign="bottom" height={36} iconType="circle" />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                   <Typography color="text.secondary">No report data available to chart.</Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Actions / Info Section */}
        <Grid item xs={12} md={5} lg={4}>
          <Card className="fade-in-up" sx={{ animationDelay: '500ms', height: '100%', boxShadow: '0 4px 20px 0 rgba(0,0,0,0.2)' }}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
                Quick Actions
              </Typography>
              <Divider sx={{ mb: 3 }} />
              
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Paper 
                  elevation={0}
                  sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', background: 'rgba(0, 212, 255, 0.05)', border: '1px solid rgba(0, 212, 255, 0.2)', transition: 'all 0.2s', '&:hover': { background: 'rgba(0, 212, 255, 0.1)', transform: 'translateY(-2px)' } }}
                  onClick={() => navigate('/upload')}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                     <CloudUpload sx={{ color: '#00D4FF' }} />
                     <Typography fontWeight={600}>Upload Reports</Typography>
                  </Box>
                  <ArrowForward sx={{ color: 'text.secondary' }} />
                </Paper>

                <Paper 
                  elevation={0}
                  sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', background: 'rgba(124, 77, 255, 0.05)', border: '1px solid rgba(124, 77, 255, 0.2)', transition: 'all 0.2s', '&:hover': { background: 'rgba(124, 77, 255, 0.1)', transform: 'translateY(-2px)' } }}
                  onClick={() => navigate('/reports')}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                     <Description sx={{ color: '#7C4DFF' }} />
                     <Typography fontWeight={600}>View All Reports</Typography>
                  </Box>
                  <ArrowForward sx={{ color: 'text.secondary' }} />
                </Paper>
                
                <Paper 
                  elevation={0}
                  sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', background: 'rgba(0, 230, 118, 0.05)', border: '1px solid rgba(0, 230, 118, 0.2)', transition: 'all 0.2s', '&:hover': { background: 'rgba(0, 230, 118, 0.1)', transform: 'translateY(-2px)' } }}
                  onClick={() => navigate('/agencies')}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                     <Business sx={{ color: '#00E676' }} />
                     <Typography fontWeight={600}>Manage Agencies</Typography>
                  </Box>
                  <ArrowForward sx={{ color: 'text.secondary' }} />
                </Paper>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Uploads Table */}
      <Card className="fade-in-up" sx={{ animationDelay: '600ms', boxShadow: '0 4px 20px 0 rgba(0,0,0,0.2)' }}>
        <CardContent sx={{ p: 0 }}>
          <Box sx={{ p: 3, pb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CloudUpload sx={{ color: '#00D4FF' }} />
              <Typography variant="h6" fontWeight={700}>
                Recent Uploads
              </Typography>
            </Box>
            <Button size="small" endIcon={<ArrowForward />} onClick={() => navigate('/reports')}>
              View All
            </Button>
          </Box>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow sx={{ background: 'rgba(255,255,255,0.02)' }}>
                  <TableCell sx={{ fontWeight: 600 }}>File Details</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Size</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Upload Date</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stats?.recent_uploads?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} align="center" sx={{ py: 6 }}>
                      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: 0.5 }}>
                        <InsertDriveFile sx={{ fontSize: 48, mb: 1 }} />
                        <Typography variant="body1">No reports uploaded yet</Typography>
                      </Box>
                    </TableCell>
                  </TableRow>
                ) : (
                  stats?.recent_uploads?.map((report) => (
                    <TableRow
                      key={report.report_id}
                      sx={{
                        transition: 'background 0.2s',
                        '&:hover': { backgroundColor: 'rgba(0,212,255,0.04)' },
                      }}
                    >
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          {getFileIcon(report.original_filename)}
                          <Box>
                            <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: 350 }}>
                              {report.original_filename}
                            </Typography>
                            {report.agency_name && (
                              <Typography variant="caption" color="text.secondary">
                                {report.agency_name}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary" fontWeight={500}>
                          {(report.file_size / 1024).toFixed(1)} KB
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={report.upload_status}
                          color={muiStatusColor[report.upload_status] || 'default'}
                          size="small"
                          sx={{ fontWeight: 700, fontSize: '0.75rem', px: 1 }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary" fontWeight={500}>
                          {new Date(report.created_at).toLocaleDateString(undefined, {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
}

export default DashboardPage;

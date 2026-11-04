import { useQuery } from '@tanstack/react-query';
import React, { useEffect, useState } from 'react';
import {
  Box, Backdrop, CircularProgress, Card, CardContent, Grid, Typography, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Chip, Skeleton, Tooltip, Alert,
  IconButton, Dialog, DialogTitle, DialogContent
} from '@mui/material';
import {
  Timeline, Assessment, BubbleChart, ReportProblem, ErrorOutline,
  DragIndicator, OpenInFull, Close
} from '@mui/icons-material';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis
} from 'recharts';
import api from '../api/axios';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, rectSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

function ChartCard({ title, icon, children, delay = 0, sx: sxProp = {}, onExpand, dragHandleProps = {} }) {
  return (
    <Card className="fade-in-up" sx={{ animationDelay: `${delay}ms`, minHeight: 380, height: '100%', display: 'flex', flexDirection: 'column', ...sxProp }}>
      <CardContent sx={{ p: 2, pb: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box className="drag-handle" {...dragHandleProps} sx={{ cursor: 'grab', display: 'flex', alignItems: 'center', color: 'text.secondary', '&:active': { cursor: 'grabbing' } }}>
            <DragIndicator sx={{ fontSize: 20 }} />
          </Box>
          {icon && React.cloneElement(icon, { sx: { color: '#00D4FF', fontSize: 20 } })}
          <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
            {title}
          </Typography>
        </Box>
        {onExpand && (
          <IconButton size="small" onClick={onExpand} sx={{ color: 'text.secondary', '&:hover': { color: '#00D4FF', bgcolor: 'rgba(0,212,255,0.1)' } }}>
            <OpenInFull sx={{ fontSize: 18 }} />
          </IconButton>
        )}
      </CardContent>
      <Box sx={{ p: 2, flex: 1, position: 'relative', minHeight: 300, width: '100%' }}>
        <Box sx={{ position: 'absolute', top: 16, left: 16, right: 16, bottom: 16 }}>
          {children}
        </Box>
      </Box>
    </Card>
  );
}

function SortableWidget({ id, children, md }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    height: '100%', minHeight: 380, zIndex: transform ? 1 : 0,
    position: 'relative'
  };
  return (
    <Grid item xs={12} md={md} ref={setNodeRef} style={style}>
      {React.cloneElement(children, { dragHandleProps: { ...attributes, ...listeners } })}
    </Grid>
  );
}


const GlassTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <Box sx={{
        background: 'rgba(10, 14, 23, 0.8)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(0, 212, 255, 0.2)',
        borderRadius: 2, p: 2,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}>
        <Typography variant="subtitle2" sx={{ color: '#E2E8F0', mb: 1, fontWeight: 700 }}>{label}</Typography>
        {payload.map((entry, index) => (
          <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color }} />
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {entry.name}: <span style={{ color: '#fff', fontWeight: 600 }}>{entry.value}</span>
            </Typography>
          </Box>
        ))}
      </Box>
    );
  }
  return null;
};

export default function MLAnalyticsDashboardPage() {
  const [forecast, setForecast] = useState(null);
  const [clusters, setClusters] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [prioritize, setPrioritize] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [expandedWidget, setExpandedWidget] = useState(null);
  const initialWidgets = ['forecast', 'clusters', 'prioritize', 'anomalies'];
  const [widgets, setWidgets] = useState(initialWidgets);

  const widgetWidths = { forecast: 6, clusters: 6, prioritize: 7, anomalies: 5 };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (active.id !== over.id) {
      setWidgets((items) => {
        const oldIndex = items.indexOf(active.id);
        const newIndex = items.indexOf(over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };

    const { data, isFetching } = useQuery({
    queryKey: ['mlAnalyticsData'],
    queryFn: async () => {
      const [fRes, cRes, aRes, pRes] = await Promise.allSettled([
        api.get('/api/ml/forecast?months=6'),
        api.get('/api/ml/clusters'),
        api.get('/api/ml/anomalies'),
        api.get('/api/ml/prioritize')
      ]);
      return {
        forecast: fRes.status === 'fulfilled' ? fRes.value.data : null,
        clusters: cRes.status === 'fulfilled' ? cRes.value.data : null,
        anomalies: aRes.status === 'fulfilled' ? aRes.value.data : null,
        prioritize: pRes.status === 'fulfilled' ? pRes.value.data : null
      };
    },
    staleTime: 5 * 60 * 1000
  });

  useEffect(() => {
    if (data) {
      if (data.forecast) setForecast(data.forecast);
      if (data.clusters) setClusters(data.clusters);
      if (data.anomalies) setAnomalies(data.anomalies);
      if (data.prioritize) setPrioritize(data.prioritize);
      setLoading(false);
    }
  }, [data]);

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" fontWeight={800} sx={{ mb: 4 , background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>AI Risk Analytics</Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}><Skeleton variant="rounded" height={300} sx={{ borderRadius: 3 }} /></Grid>
          <Grid item xs={12} md={6}><Skeleton variant="rounded" height={300} sx={{ borderRadius: 3 }} /></Grid>
          <Grid item xs={12}><Skeleton variant="rounded" height={400} sx={{ borderRadius: 3 }} /></Grid>
        </Grid>
      </Box>
    );
  }

  // Formatting Forecast Data
  let forecastData = [];
  if (forecast?.status === 'success') {
    const hist = forecast.historical.map(d => ({ date: d.date, actual: d.count }));
    const pred = forecast.forecast.map(d => ({ date: d.date, predicted: d.count }));
    const allDates = [...new Set([...hist.map(h=>h.date), ...pred.map(p=>p.date)])].sort();
    forecastData = allDates.map(date => {
      const h = hist.find(x => x.date === date);
      const p = pred.find(x => x.date === date);
      return { date, actual: h?.actual, predicted: p?.predicted };
    });
  }

  // Formatting Cluster Data
  let clusterData = [];
  if (clusters?.status === 'success') {
    clusterData = clusters.agencies.map(a => ({
      name: a.agency_name,
      cluster: a.cluster,
      x: a.metrics.total_reports,
      y: a.metrics.avg_cvss,
      z: a.metrics.severity_density
    }));
  }

  
  const renderWidget = (key) => {
    switch(key) {
    case 'forecast':
      return (
        <ChartCard title="6-Month Vulnerability Forecast" icon={<Timeline />} delay={100} onExpand={() => setExpandedWidget('forecast')}>
            {forecast?.status === 'insufficient_data' ? (
              <Alert severity="info">{forecast.message}</Alert>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={forecastData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="date" stroke="rgba(255,255,255,0.5)" />
                  <YAxis stroke="rgba(255,255,255,0.5)" />
                  <RechartsTooltip content={<GlassTooltip />} />
                  <Line type="monotone" dataKey="actual" name="Historical" stroke="#00E676" strokeWidth={3} dot={{r: 4}} />
                  <Line type="monotone" dataKey="predicted" name="Forecast (Prophet)" stroke="#7C4DFF" strokeWidth={3} strokeDasharray="5 5" dot={{r: 4}} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
      );
    case 'clusters':
      return (
        <ChartCard title="Agency Risk Clustering (HDBSCAN)" icon={<BubbleChart />} delay={200} onExpand={() => setExpandedWidget('clusters')}>
            {clusters?.status === 'insufficient_data' ? (
              <Alert severity="info">{clusters.message}</Alert>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="x" type="number" name="Total Reports" stroke="rgba(255,255,255,0.5)" />
                  <YAxis dataKey="y" type="number" name="Avg CVSS" stroke="rgba(255,255,255,0.5)" />
                  <ZAxis dataKey="z" type="number" range={[50, 400]} name="Severity Density" />
                  <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} />
                  <Scatter name="Agencies" data={clusterData} fill="#00D4FF" />
                </ScatterChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
      );
    case 'prioritize':
      return (
        <ChartCard title="Prioritized Action Queue (TOPSIS)" icon={<ReportProblem />} delay={300} onExpand={() => setExpandedWidget('prioritize')}>
            <Box sx={{ flex: 1, overflowY: 'auto' }}>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Vulnerability</TableCell>
                      <TableCell>CVSS</TableCell>
                      <TableCell>Days Open</TableCell>
                      <TableCell>Priority Score</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {prioritize?.data?.length === 0 ? (
                      <TableRow><TableCell colSpan={4} align="center">No open tasks</TableCell></TableRow>
                    ) : (
                      prioritize?.data?.map((task) => (
                        <TableRow key={task.finding_id}>
                          <TableCell sx={{ maxWidth: 200 }}><Typography noWrap variant="body2">{task.title}</Typography></TableCell>
                          <TableCell>{task.cvss}</TableCell>
                          <TableCell>{task.days_open}</TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Box sx={{ width: '100%', height: 6, bgcolor: 'rgba(255,255,255,0.1)', borderRadius: 3 }}>
                                <Box sx={{ width: `${task.priority_score}%`, height: '100%', bgcolor: task.priority_score > 70 ? '#FF1744' : task.priority_score > 40 ? '#FF9100' : '#00E676', borderRadius: 3 }} />
                              </Box>
                              <Typography variant="caption">{task.priority_score}</Typography>
                            </Box>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          </ChartCard>
      );
    case 'anomalies':
      return (
        <ChartCard title="Anomalous Agencies (Isolation Forest)" icon={<ErrorOutline />} delay={400} onExpand={() => setExpandedWidget('anomalies')}>
            {anomalies?.status === 'insufficient_data' ? (
              <Alert severity="info">{anomalies.message}</Alert>
            ) : (
              <Box sx={{ flex: 1, overflowY: 'auto' }}>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Agency</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Score</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {anomalies?.data?.map((agency) => (
                        <TableRow key={agency.agency_id}>
                          <TableCell><Typography noWrap variant="body2">{agency.agency_name}</Typography></TableCell>
                          <TableCell>
                            {agency.is_anomaly ? (
                              <Chip size="small" label="Outlier" color="error" />
                            ) : (
                              <Chip size="small" label="Normal" color="success" />
                            )}
                          </TableCell>
                          <TableCell>{agency.anomaly_score.toFixed(2)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            )}
          </ChartCard>
      );

      default: return null;
    }
  };

  return (
    <Box>
      <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Assessment sx={{ fontSize: 40, color: '#00D4FF' }} />
        <Box>
          <Typography variant="h4" fontWeight={800}>AI Risk Analytics (Air-Gapped)</Typography>
          <Typography variant="body2" color="text.secondary">
            Mathematical Forecasting, Clustering, and Task Prioritization without external models
          </Typography>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      
      {/* ═══════ DRAGGABLE WIDGETS ═══════ */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={widgets} strategy={rectSortingStrategy}>
          <Grid container spacing={3}>
            {widgets.map(key => (
              <SortableWidget key={key} id={key} md={widgetWidths[key]}>
                {renderWidget(key)}
              </SortableWidget>
            ))}
          </Grid>
        </SortableContext>
      </DndContext>


      {/* Expand Dialog */}
      <Dialog 
        open={Boolean(expandedWidget)} 
        onClose={() => setExpandedWidget(null)} 
        maxWidth="lg" 
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: '#0B1120',
            border: '1px solid rgba(255,255,255,0.1)',
            backgroundImage: 'none',
            height: '80vh',
            display: 'flex',
            flexDirection: 'column'
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.05)', p: 2 }}>
          <Typography variant="h6" fontWeight={700}>Expanded View</Typography>
          <IconButton onClick={() => setExpandedWidget(null)} sx={{ color: 'text.secondary' }}>
            <Close />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 3, flex: 1, minHeight: 0 }}>
          {expandedWidget === 'forecast' && (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.5)" />
                <YAxis stroke="rgba(255,255,255,0.5)" />
                <RechartsTooltip content={<GlassTooltip />} />
                <Line type="monotone" dataKey="actual" name="Historical" stroke="#00E676" strokeWidth={3} dot={{r: 4}} />
                <Line type="monotone" dataKey="predicted" name="Forecast" stroke="#7C4DFF" strokeWidth={3} strokeDasharray="5 5" dot={{r: 4}} />
              </LineChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'clusters' && (
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="x" type="number" name="Total Reports" stroke="rgba(255,255,255,0.5)" />
                <YAxis dataKey="y" type="number" name="Avg CVSS" stroke="rgba(255,255,255,0.5)" />
                <ZAxis dataKey="z" type="number" range={[100, 1000]} name="Severity Density" />
                <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} />
                <Scatter name="Agencies" data={clusterData} fill="#00D4FF" />
              </ScatterChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'prioritize' && (
            <TableContainer sx={{ height: '100%' }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Vulnerability</TableCell>
                    <TableCell>CVSS</TableCell>
                    <TableCell>Days Open</TableCell>
                    <TableCell>Priority Score</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {prioritize?.data?.map((task) => (
                    <TableRow key={task.finding_id}>
                      <TableCell>{task.title}</TableCell>
                      <TableCell>{task.cvss}</TableCell>
                      <TableCell>{task.days_open}</TableCell>
                      <TableCell>{task.priority_score}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          {expandedWidget === 'anomalies' && (
            <TableContainer sx={{ height: '100%' }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Agency</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Score</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {anomalies?.data?.map((agency) => (
                    <TableRow key={agency.agency_id}>
                      <TableCell>{agency.agency_name}</TableCell>
                      <TableCell>{agency.is_anomaly ? 'Outlier' : 'Normal'}</TableCell>
                      <TableCell>{agency.anomaly_score.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}

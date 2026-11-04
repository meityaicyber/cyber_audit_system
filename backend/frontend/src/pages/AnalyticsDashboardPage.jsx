import { useQuery } from '@tanstack/react-query';
import React, { useState, useMemo, useEffect } from 'react';
import {
  Box, Backdrop, CircularProgress,
  Card,
  CardContent,
  Grid,
  Typography,
  Skeleton,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  alpha,
  useTheme,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  ListItemText,
  OutlinedInput,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import {
  BugReport,
  ErrorOutline,
  CheckCircleOutline,
  Speed,
  Shield,
  Assessment,
  TrendingUp,
  Category,
  Layers,
  Repeat,
  Storage,
  GppBad,
  Download,
  DragIndicator,
  OpenInFull,
  Close,
} from '@mui/icons-material';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
} from 'recharts';
import api from '../api/axios';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  rectSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

/* ─────────────────────── Color Palettes ─────────────────────── */
const SEVERITY_COLORS = {
  CRITICAL: '#FF1744',
  HIGH: '#FF9100',
  MEDIUM: '#FFD600',
  LOW: '#00E676',
  INFORMATIONAL: '#7C4DFF',
};

const STATUS_COLORS = {
  OPEN: '#FF1744',
  CLOSED: '#00E676',
  ACCEPTED: '#7C4DFF',
  RISK_ACCEPTED: '#FF9100',
  IN_PROGRESS: '#00D4FF',
  'PARTIALLY REMEDIATED': '#FFD600',
};

const ENUM_LABELS = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
  INFORMATIONAL: 'Informational',
  OPEN: 'Open',
  CLOSED: 'Closed',
  ACCEPTED: 'Accepted',
  RISK_ACCEPTED: 'Risk Accepted',
  IN_PROGRESS: 'In Progress',
  'PARTIALLY REMEDIATED': 'Partially Remediated',
};

function formatEnumLabel(label) {
  if (!label) return 'N/A';
  return ENUM_LABELS[label] || label;
}

const CHART_COLORS = [
  '#00D4FF',
  '#7C4DFF',
  '#FF9100',
  '#00E676',
  '#FF1744',
  '#FFD600',
  '#E040FB',
  '#18FFFF',
  '#FF6E40',
  '#76FF03',
  '#448AFF',
  '#FFAB40',
  '#FF4081',
  '#69F0AE',
  '#B388FF',
];

/* ─────────────────── Custom Recharts Tooltip ─────────────────── */
function GlassTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <Box
      sx={{
        backgroundColor: 'rgba(17, 24, 39, 0.92)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 2,
        px: 2,
        py: 1.2,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}
    >
      {label && (
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          {label}
        </Typography>
      )}
      {payload.map((entry, idx) => (
        <Typography key={idx} variant="body2" sx={{ color: entry.color || '#E2E8F0', fontWeight: 600 }}>
          {formatEnumLabel(entry.name)}: {entry.value}
        </Typography>
      ))}
    </Box>
  );
}

/* ─────────────────── Animated Counter ─────────────────── */
function AnimatedNumber({ value, duration = 1200 }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (value == null) return;
    const target = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(target)) {
      setDisplay(value);
      return;
    }
    let start = 0;
    const startTime = performance.now();
    function step(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(eased * target * 10) / 10;
      setDisplay(Number.isInteger(target) ? Math.round(eased * target) : current);
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, [value, duration]);

  return <>{display}</>;
}

/* ─────────────────── KPI Stat Card ─────────────────── */
function KpiCard({ title, value, icon, color, delay = 0 }) {
  return (
    <Card
      className="fade-in-up"
      sx={{
        animationDelay: `${delay}ms`,
        position: 'relative',
        overflow: 'hidden',
        minHeight: 130,
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography
              variant="caption"
              sx={{ color: 'text.secondary', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.68rem' }}
            >
              {title}
            </Typography>
            <Typography variant="h3" sx={{ fontWeight: 800, color, mt: 0.5 }}>
              <AnimatedNumber value={value} />
            </Typography>
          </Box>
          <Box
            sx={{
              p: 1.2,
              borderRadius: 2,
              background: alpha(color, 0.12),
              display: 'flex',
            }}
          >
            {React.cloneElement(icon, { sx: { fontSize: 26, color } })}
          </Box>
        </Box>
      </CardContent>
      <Box
        sx={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: 3,
          background: `linear-gradient(90deg, ${color}, transparent)`,
        }}
      />
    </Card>
  );
}

/* ─────────────────── Chart Card Wrapper ─────────────────── */
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

/* ─────────────────── Severity Badge ─────────────────── */
function SeverityBadge({ severity }) {
  const color = SEVERITY_COLORS[severity] || '#94A3B8';
  return (
    <Chip
      label={formatEnumLabel(severity)}
      size="small"
      sx={{
        fontWeight: 600,
        fontSize: '0.7rem',
        backgroundColor: alpha(color, 0.15),
        color,
        border: `1px solid ${alpha(color, 0.3)}`,
      }}
    />
  );
}

/* ─────────────────── Status Badge ─────────────────── */
function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] || '#94A3B8';
  return (
    <Chip
      label={formatEnumLabel(status)}
      size="small"
      sx={{
        fontWeight: 600,
        fontSize: '0.7rem',
        backgroundColor: alpha(color, 0.12),
        color,
        border: `1px solid ${alpha(color, 0.25)}`,
      }}
    />
  );
}

/* ─────────────────── Pie / Donut Label ─────────────────── */
function renderDonutLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }) {
  if (percent < 0.05) return null;
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="#E2E8F0" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN PAGE COMPONENT
   ═══════════════════════════════════════════════════════════════ */
export default function AnalyticsDashboardPage() {
  const [viewMode, setViewMode] = useState('GLOBAL');
  const [selectedAgencyId, setSelectedAgencyId] = useState('');
  const [selectedFileId, setSelectedFileId] = useState('');
  const [selectedSeverities, setSelectedSeverities] = useState([]);
  const [selectedStatuses, setSelectedStatuses] = useState([]);
  const [timeRange, setTimeRange] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [chartFilter, setChartFilter] = useState({ key: null, value: null });
  
  const [agencies, setAgencies] = useState([]);
  const [files, setFiles] = useState([]);
  const [allVulns, setAllVulns] = useState([]);

  const [expandedWidget, setExpandedWidget] = useState(null);

  const initialWidgets = [
    'severity', 'status',
    'cvss', 'trend',
    'category', 'cwe',
    'cve', 'asset',
    'newrepeat', 'table'
  ];
  const [widgets, setWidgets] = useState(initialWidgets);

  const widgetWidths = {
    severity: 6, status: 6,
    cvss: 6, trend: 6,
    category: 6, cwe: 6,
    cve: 6, asset: 6,
    newrepeat: 4, table: 8
  };

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

  const handleChartClick = (key, value) => {
    if (chartFilter.key === key && chartFilter.value === value) {
      setChartFilter({ key: null, value: null });
    } else {
      setChartFilter({ key, value });
    }
  };

  const handleExportCsv = () => {
    if (!tableVulns || tableVulns.length === 0) return;

    const headers = ['ID', 'Title', 'Severity', 'Status', 'CVSS', 'Date Found', 'Category', 'CWE', 'CVE', 'Asset', 'New or Repeat'];
    const escapeCsv = (str) => {
      if (str == null) return '';
      const text = String(str).replace(/"/g, '""');
      return `"${text}"`;
    };

    const rows = tableVulns.map(v => [
      escapeCsv(v.id),
      escapeCsv(v.title),
      escapeCsv(v.severity),
      escapeCsv(v.status),
      escapeCsv(v.cvss),
      escapeCsv(new Date(v.date).toLocaleDateString()),
      escapeCsv(v.category),
      escapeCsv(v.cwe),
      escapeCsv(v.cve),
      escapeCsv(v.asset),
      escapeCsv(v.new_or_repeat)
    ]);

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('  const aggregatedData = data?.aggregates || {};n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Security_Analytics_Export_${new Date().getTime()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  const { data, isFetching } = useQuery({
    queryKey: ['analyticsData', viewMode, selectedAgencyId, selectedFileId, timeRange, selectedSeverities, selectedStatuses],
    queryFn: async () => {
      let queryParams = new URLSearchParams();
      if (viewMode === 'AGENCY' && selectedAgencyId) queryParams.append('agency_id', selectedAgencyId);
      if (viewMode === 'FILE' && selectedFileId) queryParams.append('report_id', selectedFileId);
      if (timeRange && timeRange !== 'ALL') queryParams.append('time_range', timeRange);
      selectedSeverities.forEach(s => queryParams.append('severities', s));
      selectedStatuses.forEach(s => queryParams.append('statuses', s));
      const qs = queryParams.toString() ? '?' + queryParams.toString() : '';

      const [agenciesRes, reportsRes, aggRes, vulnsRes] = await Promise.all([
        api.get('/api/agencies?limit=100'),
        api.get('/api/reports?limit=100'),
        api.get('/api/analytics/dashboard-aggregates' + qs),
        api.get('/api/analytics/vulnerabilities-raw' + qs + (qs ? '&' : '?') + 'page=1&limit=100')
      ]);
      
      return {
        agencies: agenciesRes.data.agencies.map(a => ({ id: a.agency_id, name: a.agency_name })),
        reports: reportsRes.data.reports.map(r => ({
          id: r.report_id,
          name: r.original_filename,
          date: r.created_at,
          agencyId: r.agency ? r.agency.agency_id : null,
        })),
        aggregates: aggRes.data,
        tableVulns: vulnsRes.data.data
      };
    },
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (data) {
      setAgencies(data.agencies);
      setFiles(data.reports);
      setLoading(false);
    }
  }, [data]);

  useEffect(() => {
    setSelectedFileId('');
  }, [selectedAgencyId]);
  const aggregatedData = data?.aggregates || {};
  let { summary = {}, severityDist, statusDist, cvssDist, trend, categories, topCwe, topCve, assets, newRepeat } = aggregatedData;
  const rawTableVulns = data?.tableVulns || [];
  
  const tableVulns = React.useMemo(() => {
    let vulns = [...rawTableVulns];
    if (chartFilter.key && chartFilter.value) {
      if (chartFilter.key === 'cvss') {
        const [minStr, maxStr] = chartFilter.value.split('-');
        const minVal = parseFloat(minStr);
        const maxVal = parseFloat(maxStr);
        vulns = vulns.filter(v => {
          if (v.cvss == null) return false;
          // E.g. '7-8' means 7 <= cvss < 8, or 9-10 means 9 <= cvss <= 10
          if (maxVal === 10) return v.cvss >= minVal && v.cvss <= maxVal;
          return v.cvss >= minVal && v.cvss < maxVal;
        });
      } else {
        vulns = vulns.filter(v => {
          const vVal = v[chartFilter.key];
          if (typeof vVal === 'string' && typeof chartFilter.value === 'string') {
            return vVal.toUpperCase() === chartFilter.value.toUpperCase();
          }
          return vVal === chartFilter.value;
        });
      }
    }
    return vulns;
  }, [rawTableVulns, chartFilter]);

  if (chartFilter.key && chartFilter.value) {
    const countBy = (arr, key) => {
      const counts = {};
      arr.forEach(item => {
        let val = item[key];
        if (val != null) {
          if (typeof val === 'string' && (key === 'severity' || key === 'status')) {
            val = val.toUpperCase();
          }
          counts[val] = (counts[val] || 0) + 1;
        }
      });
      return counts;
    };
    const mapToDist = (counts, keyName) => Object.keys(counts).map(k => ({ [keyName]: k, count: counts[k] })).sort((a,b)=>b.count-a.count);
    
    severityDist = mapToDist(countBy(tableVulns, 'severity'), 'severity');
    statusDist = mapToDist(countBy(tableVulns, 'status'), 'status');
    categories = mapToDist(countBy(tableVulns, 'category'), 'category').slice(0, 10);
    topCwe = mapToDist(countBy(tableVulns, 'cwe'), 'cwe_id').slice(0, 10);
    topCve = mapToDist(countBy(tableVulns, 'cve'), 'cve_id').slice(0, 10);
    assets = mapToDist(countBy(tableVulns, 'asset'), 'asset').slice(0, 10);
    newRepeat = mapToDist(countBy(tableVulns, 'new_or_repeat'), 'type');

    const cvssCounts = {'0-1':0, '1-2':0, '2-3':0, '3-4':0, '4-5':0, '5-6':0, '6-7':0, '7-8':0, '8-9':0, '9-10':0};
    tableVulns.forEach(v => {
      const s = v.cvss;
      if (s != null) {
        let bucket = Math.floor(s);
        if (bucket > 9) bucket = 9;
        if (bucket < 0) bucket = 0;
        cvssCounts[`${bucket}-${bucket+1}`]++;
      }
    });
    cvssDist = Object.keys(cvssCounts).map(k => ({ range: k, count: cvssCounts[k] }));

    let sumCvss = 0;
    let countCvss = 0;
    tableVulns.forEach(v => {
      if (v.cvss != null) { sumCvss += v.cvss; countCvss++; }
    });

    summary = {
      total_detailed_observations: tableVulns.length,
      open_detailed_observations: tableVulns.filter(v => v.status === 'OPEN').length,
      closed_detailed_observations: tableVulns.filter(v => v.status === 'CLOSED').length,
      avg_cvss_score: countCvss > 0 ? (sumCvss / countCvss).toFixed(1) : 0,
      critical_count: tableVulns.filter(v => v.severity === 'CRITICAL').length,
      reports_with_detailed_observations: new Set(tableVulns.map(v => v.report_id || v.id)).size
    };
  }
const columns = [
    { field: 'title', headerName: 'Title', flex: 1, minWidth: 200, renderCell: (params) => (
      <Typography variant="body2" fontWeight={500} noWrap sx={{ fontSize: '0.8rem' }}>
        {params.value}
      </Typography>
    )},
    { field: 'severity', headerName: 'Severity', width: 130, renderCell: (params) => <SeverityBadge severity={params.value} /> },
    { field: 'status', headerName: 'Status', width: 130, renderCell: (params) => <StatusBadge status={params.value} /> },
    { field: 'cvss', headerName: 'CVSS', width: 90, type: 'number', renderCell: (params) => (
      <Typography
        variant="body2"
        sx={{
          fontWeight: 700,
          fontSize: '0.8rem',
          color: params.value >= 9 ? '#FF1744' : params.value >= 7 ? '#FF9100' : params.value >= 4 ? '#FFD600' : '#00E676',
        }}
      >
        {params.value != null ? params.value.toFixed(1) : '—'}
      </Typography>
    ) },
    { field: 'date', headerName: 'Date', width: 110, renderCell: (params) => new Date(params.value).toLocaleDateString() },
  ];

  /* ─── Loading skeleton ─── */
  if (loading) {
    
  
  return (
    <Box>
      <Backdrop open={isFetching} sx={{ color: '#00D4FF', zIndex: 9999, flexDirection: 'column', gap: 2, background: 'rgba(10,14,23,0.8)' }}>
        <CircularProgress color='inherit' />
        <Typography variant='h6' fontWeight={600}>Fetching Live Data...</Typography>
      </Backdrop>
        <Skeleton variant="text" width={260} height={42} sx={{ mb: 1 }} />
        <Skeleton variant="text" width={380} height={24} sx={{ mb: 3 }} />
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Grid item xs={12} sm={6} md={4} lg={2} key={i}>
              <Skeleton variant="rounded" height={130} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
        <Grid container spacing={2.5}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Grid item xs={12} md={6} key={i}>
              <Skeleton variant="rounded" height={340} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  const handleTabChange = (event, newValue) => {
    setViewMode(newValue);
    if (newValue === 'GLOBAL') {
      setSelectedAgencyId('');
      setSelectedFileId('');
    }
  };

  const agencyFiles = files.filter(f => f.agencyId === selectedAgencyId);


  const renderWidget = (key) => {
    switch(key) {
    case 'severity':
      return (
        <ChartCard title="Severity Distribution" icon={<Shield />} delay={350} onExpand={() => setExpandedWidget('severity')}>
            {severityDist && severityDist.some((d) => d.count > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityDist}
                    dataKey="count"
                    nameKey="severity"
                    cx="50%"
                    cy="50%"
                    innerRadius="50%"
                    outerRadius="80%"
                    paddingAngle={3}
                    labelLine={false}
                    label={renderDonutLabel}
                    animationBegin={0}
                    animationDuration={1000}
                    animationEasing="ease-out"
                  >
                    {severityDist.map((entry) => (
                      <Cell 
                        key={entry.severity} 
                        fill={SEVERITY_COLORS[entry.severity] || '#94A3B8'} 
                        stroke="none" 
                        onClick={() => handleChartClick('severity', entry.severity)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'severity' && chartFilter.value !== entry.severity ? 0.3 : 1 }}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<GlassTooltip />} />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle"
                    iconSize={8}
                    formatter={(val) => <span style={{ color: '#94A3B8', fontSize: 12 }}>{val}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'status':
      return (
        <ChartCard title="Vulnerability Status" icon={<Layers />} delay={400} onExpand={() => setExpandedWidget('status')}>
            {statusDist && statusDist.some((d) => d.count > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusDist}
                    dataKey="count"
                    nameKey="status"
                    cx="50%"
                    cy="50%"
                    innerRadius="50%"
                    outerRadius="80%"
                    paddingAngle={3}
                    labelLine={false}
                    label={renderDonutLabel}
                    animationBegin={0}
                    animationDuration={1000}
                    animationEasing="ease-out"
                  >
                    {statusDist.map((entry) => (
                      <Cell 
                        key={entry.status} 
                        fill={STATUS_COLORS[entry.status] || '#94A3B8'} 
                        stroke="none" 
                        onClick={() => handleChartClick('status', entry.status)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'status' && chartFilter.value !== entry.status ? 0.3 : 1 }}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<GlassTooltip />} />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle"
                    iconSize={8}
                    formatter={(val) => <span style={{ color: '#94A3B8', fontSize: 12 }}>{val}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'cvss':
      return (
        <ChartCard title="CVSS Score Distribution" icon={<Speed />} delay={450} onExpand={() => setExpandedWidget('cvss')}>
            {cvssDist && cvssDist.some((d) => d.count > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cvssDist} barSize={28}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="range" tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} />
                  <YAxis tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} allowDecimals={false} />
                  <Tooltip content={<GlassTooltip />} />
                  <Bar dataKey="count" name="Vulnerabilities" radius={[4, 4, 0, 0]} animationDuration={1000}>
                    {cvssDist.map((entry, idx) => {
                      const colors = ['#00E676', '#00E676', '#69F0AE', '#FFD600', '#FFD600', '#FF9100', '#FF9100', '#FF1744', '#FF1744', '#D50000'];
                      return <Cell 
                        key={idx} 
                        fill={colors[idx]} 
                        onClick={() => handleChartClick('cvss', entry.range)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'cvss' && chartFilter.value !== entry.range ? 0.3 : 1 }}
                      />;
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'trend':
      return (
        <ChartCard title="Vulnerability Trend (12 Months)" icon={<TrendingUp />} delay={500} onExpand={() => setExpandedWidget('trend')}>
            {trend && trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend}>
                  <defs>
                    <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00D4FF" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#00D4FF" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="month" tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} />
                  <YAxis tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} allowDecimals={false} />
                  <Tooltip content={<GlassTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    name="Vulnerabilities"
                    stroke="#00D4FF"
                    strokeWidth={2.5}
                    fill="url(#trendGrad)"
                    dot={{ fill: '#00D4FF', r: 4, strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: '#00D4FF', stroke: '#0A0E17', strokeWidth: 2 }}
                    animationDuration={1200}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState message="No trend data available" />
            )}
          </ChartCard>
      );
    case 'category':
      return (
        <ChartCard title="Top Vulnerability Categories" icon={<Category />} delay={550} onExpand={() => setExpandedWidget('category')}>
            {categories && categories.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categories} layout="vertical" barSize={16} margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} allowDecimals={false} />
                  <YAxis
                    dataKey="category"
                    type="category"
                    width={160}
                    tick={{ fill: '#94A3B8', fontSize: 11 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                    tickFormatter={(val) => (val.length > 22 ? `${val.substring(0, 22)}…` : val)}
                  />
                  <Tooltip content={<GlassTooltip />} />
                  <Bar dataKey="count" name="Count" radius={[0, 4, 4, 0]} animationDuration={1000}>
                    {categories.map((entry, idx) => (
                      <Cell 
                        key={idx} 
                        fill={CHART_COLORS[idx % CHART_COLORS.length]} 
                        onClick={() => handleChartClick('category', entry.category)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'category' && chartFilter.value !== entry.category ? 0.3 : 1 }}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'cwe':
      return (
        <ChartCard title="Top CWE Weaknesses" icon={<Shield />} delay={600} onExpand={() => setExpandedWidget('cwe')}>
            {topCwe && topCwe.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topCwe} barSize={24}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="cwe_id" tick={{ fill: '#94A3B8', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} angle={-30} textAnchor="end" height={60} />
                  <YAxis tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} allowDecimals={false} />
                  <Tooltip content={<GlassTooltip />} />
                  <Bar dataKey="count" name="Occurrences" radius={[4, 4, 0, 0]} animationDuration={1000}>
                    {topCwe.map((entry, idx) => (
                      <Cell 
                        key={idx} 
                        fill={CHART_COLORS[idx % CHART_COLORS.length]} 
                        onClick={() => handleChartClick('cwe', entry.cwe_id)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'cwe' && chartFilter.value !== entry.cwe_id ? 0.3 : 1 }}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'cve':
      return (
        <ChartCard title="Top CVE IDs" icon={<GppBad />} delay={650} onExpand={() => setExpandedWidget('cve')}>
            {topCve && topCve.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topCve} barSize={24}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="cve_id" tick={{ fill: '#94A3B8', fontSize: 9 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} angle={-35} textAnchor="end" height={70} />
                  <YAxis tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} allowDecimals={false} />
                  <Tooltip content={<GlassTooltip />} />
                  <Bar dataKey="count" name="Occurrences" radius={[4, 4, 0, 0]} animationDuration={1000}>
                    {topCve.map((entry, idx) => (
                      <Cell 
                        key={idx} 
                        fill={CHART_COLORS[(idx + 5) % CHART_COLORS.length]} 
                        onClick={() => handleChartClick('cve', entry.cve_id)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'cve' && chartFilter.value !== entry.cve_id ? 0.3 : 1 }}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'asset':
      return (
        <ChartCard title="Most Affected Assets" icon={<Storage />} delay={700} onExpand={() => setExpandedWidget('asset')}>
            {assets && assets.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={assets} layout="vertical" barSize={16} margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} allowDecimals={false} />
                  <YAxis
                    dataKey="asset"
                    type="category"
                    width={180}
                    tick={{ fill: '#94A3B8', fontSize: 10 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                    tickFormatter={(val) => (val.length > 25 ? `${val.substring(0, 25)}…` : val)}
                  />
                  <Tooltip content={<GlassTooltip />} />
                  <Bar dataKey="count" name="Vulnerabilities" radius={[0, 4, 4, 0]} animationDuration={1000}>
                    {assets.map((entry, idx) => (
                      <Cell 
                        key={idx} 
                        fill={CHART_COLORS[(idx + 3) % CHART_COLORS.length]} 
                        onClick={() => handleChartClick('asset', entry.asset)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'asset' && chartFilter.value !== entry.asset ? 0.3 : 1 }}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'newrepeat':
      return (
        <ChartCard title="New vs Repeat Findings" icon={<Repeat />} delay={750} onExpand={() => setExpandedWidget('newrepeat')}>
            {newRepeat && newRepeat.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={newRepeat}
                    dataKey="count"
                    nameKey="type"
                    cx="50%"
                    cy="50%"
                    innerRadius="50%"
                    outerRadius="80%"
                    paddingAngle={4}
                    labelLine={false}
                    label={renderDonutLabel}
                    animationDuration={1000}
                  >
                    {newRepeat.map((entry, idx) => (
                      <Cell 
                        key={idx} 
                        fill={idx === 0 ? '#00D4FF' : '#FF9100'} 
                        stroke="none" 
                        onClick={() => handleChartClick('new_or_repeat', entry.type)}
                        style={{ cursor: 'pointer', opacity: chartFilter.key === 'new_or_repeat' && chartFilter.value !== entry.type ? 0.3 : 1 }}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<GlassTooltip />} />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle"
                    iconSize={8}
                    formatter={(val) => <span style={{ color: '#94A3B8', fontSize: 12 }}>{val}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </ChartCard>
      );
    case 'table':
      return (
        <ChartCard 
            title={`Vulnerabilities ${chartFilter.value ? `(Filtered by ${chartFilter.value})` : ''}`} 
            icon={<BugReport />} 
            delay={800}
            onExpand={() => setExpandedWidget('table')}
            sx={{
              '& .MuiDataGrid-root': {
                border: 'none',
                color: 'text.primary',
              },
              '& .MuiDataGrid-cell': {
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                display: 'flex',
                alignItems: 'center',
              },
              '& .MuiDataGrid-columnHeaders': {
                borderBottom: '1px solid rgba(255,255,255,0.1)',
                backgroundColor: 'rgba(17, 24, 39, 0.4)',
              },
              '& .MuiDataGrid-footerContainer': {
                borderTop: '1px solid rgba(255,255,255,0.1)',
              },
              '& .MuiTablePagination-root': {
                color: 'text.secondary',
              },
              '& .MuiDataGrid-iconSeparator': {
                display: 'none',
              },
            }}
          >
            {tableVulns && tableVulns.length > 0 ? (
              <Box sx={{ height: 400, width: '100%', minHeight: 400, flex: 1, overflow: 'hidden' }}>
                <DataGrid
                  rows={tableVulns}
                  columns={columns}
                  pageSizeOptions={[5, 10, 25]}
                  initialState={{
                    pagination: { paginationModel: { pageSize: 5 } },
                  }}
                  disableRowSelectionOnClick
                />
              </Box>
            ) : (
              <EmptyState message="No detailed observations match the current filters" />
            )}
          </ChartCard>
      );

      default: return null;
    }
  };

  return (
    <Box>
      {/* ── Header ── */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3.5 }}>
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ mb: 0.5 , background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>
            Security Analytics
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Vulnerability intelligence across all audited reports
          </Typography>
        </Box>
        
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Button 
            variant="contained" 
            startIcon={<Download />}
            onClick={handleExportCsv}
            sx={{
              bgcolor: 'rgba(255, 255, 255, 0.05)',
              color: 'text.primary',
              border: '1px solid rgba(255,255,255,0.1)',
              textTransform: 'none',
              fontWeight: 600,
              px: 2,
              '&:hover': {
                bgcolor: 'rgba(255, 255, 255, 0.1)',
              }
            }}
          >
            Export CSV
          </Button>
          <Box sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', borderRadius: 2, p: 0.5, border: '1px solid rgba(255,255,255,0.05)' }}>
          <Tabs 
            value={viewMode} 
            onChange={handleTabChange}
            indicatorColor="primary"
            textColor="primary"
            sx={{
              minHeight: 40,
              '& .MuiTab-root': { minHeight: 40, textTransform: 'none', fontWeight: 600, fontSize: '0.85rem' }
            }}
          >
            <Tab label="Global View" value="GLOBAL" />
            <Tab label="Agency View" value="AGENCY" />
            <Tab label="File / Report View" value="FILE" />
          </Tabs>
        </Box>
      </Box>
    </Box>

      {/* ── Filter Controls ── */}
      <Card sx={{ mb: 3.5, background: 'rgba(17, 24, 39, 0.4)', border: '1px solid rgba(255,255,255,0.05)' }}>
        <CardContent sx={{ display: 'flex', gap: 3, alignItems: 'center', flexWrap: 'wrap' }}>
          
          {/* Global Advanced Filters */}
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Time Range</InputLabel>
            <Select value={timeRange} label="Time Range" onChange={(e) => setTimeRange(e.target.value)}>
              <MenuItem value="ALL">All Time</MenuItem>
              <MenuItem value="30_DAYS">Last 30 Days</MenuItem>
              <MenuItem value="6_MONTHS">Last 6 Months</MenuItem>
              <MenuItem value="1_YEAR">Last 1 Year</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Severity Filter</InputLabel>
            <Select
              multiple
              value={selectedSeverities}
              onChange={(e) => setSelectedSeverities(e.target.value)}
              input={<OutlinedInput label="Severity Filter" />}
              renderValue={(selected) => selected.join(', ')}
            >
              {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'].map((sev) => (
                <MenuItem key={sev} value={sev}>
                  <Checkbox checked={selectedSeverities.indexOf(sev) > -1} />
                  <ListItemText primary={sev} />
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Status Filter</InputLabel>
            <Select
              multiple
              value={selectedStatuses}
              onChange={(e) => setSelectedStatuses(e.target.value)}
              input={<OutlinedInput label="Status Filter" />}
              renderValue={(selected) => selected.join(', ')}
            >
              {['OPEN', 'CLOSED', 'ACCEPTED', 'RISK_ACCEPTED', 'IN_PROGRESS'].map((stat) => (
                <MenuItem key={stat} value={stat}>
                  <Checkbox checked={selectedStatuses.indexOf(stat) > -1} />
                  <ListItemText primary={stat} />
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Scope Filters */}
          {(viewMode === 'AGENCY' || viewMode === 'FILE') && (
            <>
              <Box sx={{ borderLeft: '1px solid rgba(255,255,255,0.1)', height: 32, mx: 1 }} />
              <FormControl size="small" sx={{ minWidth: 240 }}>
                <InputLabel>Select Agency</InputLabel>
                <Select
                  value={selectedAgencyId}
                  label="Select Agency"
                  onChange={(e) => setSelectedAgencyId(e.target.value)}
                >
                  {agencies.map((agency) => (
                    <MenuItem key={agency.id} value={agency.id}>
                      {agency.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {viewMode === 'FILE' && (
                <FormControl size="small" sx={{ minWidth: 240 }}>
                  <InputLabel>Select File / Report</InputLabel>
                  <Select
                    value={selectedFileId}
                    label="Select File / Report"
                    onChange={(e) => setSelectedFileId(e.target.value)}
                  >
                    {(selectedAgencyId ? agencyFiles : files).map((file) => (
                      <MenuItem key={file.id} value={file.id}>
                        {file.name} ({new Date(file.date).toLocaleDateString()})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* ═══════ KPI SUMMARY CARDS ═══════ */}
      <Grid container spacing={2.5} sx={{ mb: 3.5 }}>
        <Grid item xs={12} sm={6} md={4} lg={2}>
          <KpiCard
            title="Total Vulns"
            value={summary?.total_detailed_observations ?? 0}
            icon={<BugReport />}
            color="#00D4FF"
            delay={0}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2}>
          <KpiCard
            title="Open"
            value={summary?.open_detailed_observations ?? 0}
            icon={<ErrorOutline />}
            color="#FF1744"
            delay={60}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2}>
          <KpiCard
            title="Closed"
            value={summary?.closed_detailed_observations ?? 0}
            icon={<CheckCircleOutline />}
            color="#00E676"
            delay={120}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2}>
          <KpiCard
            title="Avg CVSS"
            value={summary?.avg_cvss_score ?? '—'}
            icon={<Speed />}
            color="#FF9100"
            delay={180}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2}>
          <KpiCard
            title="Critical"
            value={summary?.critical_count ?? 0}
            icon={<GppBad />}
            color="#FF1744"
            delay={240}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={2}>
          <KpiCard
            title="Reports Analyzed"
            value={summary?.reports_with_detailed_observations ?? 0}
            icon={<Assessment />}
            color="#7C4DFF"
            delay={300}
          />
        </Grid>
      </Grid>

      {/* ═══════ DRAGGABLE WIDGETS ═══════ */}
      
      {/* ═══════ DRAGGABLE WIDGETS ═══════ */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={widgets} strategy={rectSortingStrategy}>
          <Grid container spacing={2.5}>
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
        <DialogContent sx={{ p: 4, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <Box sx={{ width: '100%', height: '100%', minHeight: 400 }}>
          {expandedWidget === 'severity' && (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={severityDist} dataKey="count" nameKey="severity" cx="50%" cy="50%" innerRadius="40%" outerRadius="70%" paddingAngle={3} labelLine={false} label={renderDonutLabel}>
                  {severityDist?.map((entry) => (
                    <Cell 
                      key={entry.severity} 
                      fill={SEVERITY_COLORS[entry.severity] || '#94A3B8'} 
                      stroke="none" 
                      onClick={() => handleChartClick('severity', entry.severity)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'severity' && chartFilter.value !== entry.severity ? 0.3 : 1 }}
                    />
                  ))}
                </Pie>
                <Tooltip content={<GlassTooltip />} />
                <Legend verticalAlign="bottom" />
              </PieChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'status' && (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={statusDist} dataKey="count" nameKey="status" cx="50%" cy="50%" innerRadius="40%" outerRadius="70%" paddingAngle={3} labelLine={false} label={renderDonutLabel}>
                  {statusDist?.map((entry) => (
                    <Cell 
                      key={entry.status} 
                      fill={STATUS_COLORS[entry.status] || '#94A3B8'} 
                      stroke="none" 
                      onClick={() => handleChartClick('status', entry.status)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'status' && chartFilter.value !== entry.status ? 0.3 : 1 }}
                    />
                  ))}
                </Pie>
                <Tooltip content={<GlassTooltip />} />
                <Legend verticalAlign="bottom" />
              </PieChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'cvss' && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cvssDist} barSize={40}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="range" tick={{ fill: '#94A3B8' }} />
                <YAxis tick={{ fill: '#94A3B8' }} />
                <Tooltip content={<GlassTooltip />} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {cvssDist?.map((entry, idx) => {
                    const colors = ['#00E676', '#00E676', '#69F0AE', '#FFD600', '#FFD600', '#FF9100', '#FF9100', '#FF1744', '#FF1744', '#D50000'];
                    return <Cell 
                      key={idx} 
                      fill={colors[idx]} 
                      onClick={() => handleChartClick('cvss', entry.range)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'cvss' && chartFilter.value !== entry.range ? 0.3 : 1 }}
                    />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'trend' && (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="month" tick={{ fill: '#94A3B8' }} />
                <YAxis tick={{ fill: '#94A3B8' }} />
                <Tooltip content={<GlassTooltip />} />
                <Area type="monotone" dataKey="count" stroke="#00D4FF" fill="#00D4FF" fillOpacity={0.3} />
              </AreaChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'category' && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categories} layout="vertical" margin={{ left: 50 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fill: '#94A3B8' }} />
                <YAxis dataKey="category" type="category" tick={{ fill: '#94A3B8' }} />
                <Tooltip content={<GlassTooltip />} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {categories?.map((entry, idx) => (
                    <Cell 
                      key={idx} 
                      fill={CHART_COLORS[idx % CHART_COLORS.length]} 
                      onClick={() => handleChartClick('category', entry.category)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'category' && chartFilter.value !== entry.category ? 0.3 : 1 }}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'cwe' && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topCwe} margin={{ bottom: 50 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="cwe_id" tick={{ fill: '#94A3B8' }} angle={-45} textAnchor="end" />
                <YAxis tick={{ fill: '#94A3B8' }} />
                <Tooltip content={<GlassTooltip />} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {topCwe?.map((entry, idx) => (
                    <Cell 
                      key={idx} 
                      fill={CHART_COLORS[idx % CHART_COLORS.length]} 
                      onClick={() => handleChartClick('cwe', entry.cwe_id)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'cwe' && chartFilter.value !== entry.cwe_id ? 0.3 : 1 }}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'cve' && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topCve} margin={{ bottom: 50 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="cve_id" tick={{ fill: '#94A3B8' }} angle={-45} textAnchor="end" />
                <YAxis tick={{ fill: '#94A3B8' }} />
                <Tooltip content={<GlassTooltip />} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {topCve?.map((entry, idx) => (
                    <Cell 
                      key={idx} 
                      fill={CHART_COLORS[(idx + 5) % CHART_COLORS.length]} 
                      onClick={() => handleChartClick('cve', entry.cve_id)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'cve' && chartFilter.value !== entry.cve_id ? 0.3 : 1 }}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'asset' && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={assets} layout="vertical" margin={{ left: 50 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fill: '#94A3B8' }} />
                <YAxis dataKey="asset" type="category" tick={{ fill: '#94A3B8' }} />
                <Tooltip content={<GlassTooltip />} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {assets?.map((entry, idx) => (
                    <Cell 
                      key={idx} 
                      fill={CHART_COLORS[(idx + 3) % CHART_COLORS.length]} 
                      onClick={() => handleChartClick('asset', entry.asset)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'asset' && chartFilter.value !== entry.asset ? 0.3 : 1 }}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'newrepeat' && (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={newRepeat} dataKey="count" nameKey="type" cx="50%" cy="50%" innerRadius="40%" outerRadius="70%">
                  {newRepeat?.map((entry, idx) => (
                    <Cell 
                      key={idx} 
                      fill={idx === 0 ? '#00D4FF' : '#FF9100'} 
                      onClick={() => handleChartClick('new_or_repeat', entry.type)}
                      style={{ cursor: 'pointer', opacity: chartFilter.key === 'new_or_repeat' && chartFilter.value !== entry.type ? 0.3 : 1 }}
                    />
                  ))}
                </Pie>
                <Tooltip content={<GlassTooltip />} />
                <Legend verticalAlign="bottom" />
              </PieChart>
            </ResponsiveContainer>
          )}
          {expandedWidget === 'table' && (
            <Box sx={{ height: '100%', width: '100%', 
              '& .MuiDataGrid-root': { border: 'none', color: 'text.primary' },
              '& .MuiDataGrid-cell': { borderBottom: '1px solid rgba(255,255,255,0.05)' },
              '& .MuiDataGrid-columnHeaders': { backgroundColor: 'rgba(17, 24, 39, 0.4)', borderBottom: '1px solid rgba(255,255,255,0.1)' },
            }}>
              <DataGrid rows={tableVulns || []} columns={columns} pageSizeOptions={[10, 25, 50]} />
            </Box>
          )}
          </Box>
        </DialogContent>
      </Dialog>

    </Box>
  );
}


/* ─────────────────── Empty State ─────────────────── */
function EmptyState({ message = 'No data available' }) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: 200,
        color: 'text.secondary',
      }}
    >
      <Typography variant="body2">{message}</Typography>
    </Box>
  );
}

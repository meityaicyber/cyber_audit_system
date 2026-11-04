import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  IconButton,
  TextField,
  InputAdornment,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Collapse,
  Divider,
  LinearProgress,
  Tabs,
  Tab,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Search,
  Visibility,
  Download,
  Delete,
  Description,
  RocketLaunch,
  CheckCircle,
  HourglassTop,
  Close,
  ExpandMore,
  ExpandLess,
  Shield,
  BugReport,
  Security,
  Warning,
  TipsAndUpdates,
} from '@mui/icons-material';
import { useSnackbar } from 'notistack';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/axios';

const statusColor = {
  UPLOADED: 'info',
  VALIDATED: 'success',
  REJECTED: 'error',
  QUARANTINED: 'warning',
};

const extIcon = {
  '.pdf': '📄',
  '.docx': '📝',
  '.txt': '📃',
};

const severityColor = {
  CRITICAL: '#FF1744',
  HIGH: '#FF9100',
  MEDIUM: '#FFD600',
  LOW: '#00E676',
};

const riskLevelGradient = {
  CRITICAL: 'linear-gradient(135deg, #FF1744 0%, #D50000 100%)',
  HIGH: 'linear-gradient(135deg, #FF9100 0%, #FF6D00 100%)',
  MEDIUM: 'linear-gradient(135deg, #FFD600 0%, #FFAB00 100%)',
  LOW: 'linear-gradient(135deg, #00E676 0%, #00C853 100%)',
};

/* ──────────── Pipeline Results Dialog ──────────── */
// Keeping PipelineResultsDialog unchanged...

const JsonNode = ({ label, value, defaultExpanded = false }) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  
  if (value === null || value === undefined) {
    return (
      <Box sx={{ display: 'flex', py: 0.5 }}>
        <Typography variant="body2" sx={{ color: '#90caf9', mr: 1 }}>"{label}":</Typography>
        <Typography variant="body2" sx={{ color: '#757575' }}>null</Typography>
      </Box>
    );
  }

  if (typeof value !== 'object') {
    let color = '#a5d6a7';
    if (typeof value === 'number') color = '#ffab91';
    if (typeof value === 'boolean') color = '#ce93d8';
    return (
      <Box sx={{ display: 'flex', py: 0.5, alignItems: 'flex-start' }}>
        <Typography variant="body2" sx={{ color: '#90caf9', mr: 1 }}>"{label}":</Typography>
        <Typography variant="body2" sx={{ color, wordBreak: 'break-all' }}>
          {typeof value === 'string' ? `"${value}"` : String(value)}
        </Typography>
      </Box>
    );
  }

  const isArray = Array.isArray(value);
  const keys = Object.keys(value);

  if (keys.length === 0) {
    return (
      <Box sx={{ display: 'flex', py: 0.5 }}>
        <Typography variant="body2" sx={{ color: '#90caf9', mr: 1 }}>"{label}":</Typography>
        <Typography variant="body2" sx={{ color: '#757575' }}>{isArray ? '[]' : '{}'}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ mt: 0.5 }}>
      <Box 
        onClick={() => setExpanded(!expanded)}
        sx={{ 
          display: 'flex', alignItems: 'center', cursor: 'pointer', 
          py: 0.5, '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' }, borderRadius: 1 
        }}
      >
        <Typography variant="body2" sx={{ color: '#fff', fontSize: '0.7rem', width: 20, textAlign: 'center' }}>
          {expanded ? '▼' : '▶'}
        </Typography>
        <Typography variant="body2" sx={{ color: '#90caf9', fontWeight: 600 }}>
          "{label}": {isArray ? `[${keys.length} items]` : '{ ... }'}
        </Typography>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ pl: 2, borderLeft: '1px dashed rgba(255,255,255,0.15)', ml: 1, mt: 0.5 }}>
          {keys.map((key) => (
            <JsonNode key={key} label={key} value={value[key]} />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
};

const JsonSection = ({ sectionKey, sectionData }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card elevation={0} sx={{ bgcolor: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 2 }}>
      <Box 
        onClick={() => setExpanded(!expanded)}
        sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' } }}
      >
        <Typography variant="subtitle1" fontWeight={700} sx={{ color: '#00D4FF', textTransform: 'uppercase', letterSpacing: 1 }}>
          {sectionKey.replace(/_/g, ' ')}
        </Typography>
        {expanded ? <ExpandLess /> : <ExpandMore />}
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ p: 2, pt: 0, borderTop: '1px solid rgba(255,255,255,0.05)', bgcolor: 'rgba(0,0,0,0.2)', overflowX: 'auto' }}>
          <Box sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
             {typeof sectionData === 'object' && sectionData !== null ? (
               Object.keys(sectionData).map(subKey => (
                 <JsonNode key={subKey} label={subKey} value={sectionData[subKey]} defaultExpanded={false} />
               ))
             ) : (
                <Typography variant="body2" sx={{ color: '#ccc' }}>{String(sectionData)}</Typography>
             )}
          </Box>
        </Box>
      </Collapse>
    </Card>
  );
};

const JsonSectionView = ({ data }) => {
  if (!data || typeof data !== 'object') return null;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {Object.keys(data).map((key) => (
        <JsonSection key={key} sectionKey={key} sectionData={data[key]} />
      ))}
    </Box>
  );
};
function PipelineResultsDialog({ open, onClose, results, reportName }) {
  const [tabValue, setTabValue] = useState(0);
  const [expandedSections, setExpandedSections] = useState({
    detailed_observations: true,
    compliance: false,
    recommendations: false,
  });

  if (!results) return null;

  const toggleSection = (section) =>
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));

  const execSummary = results.executive_summary || {};
  const vulnsArray = results.detailed_observations || [];
  const compliance = results.compliance || {};
  const recommendations = results.recommendations || [];
  
  const crit = vulnsArray.filter(v => (v.severity || '').toUpperCase() === 'CRITICAL').length;
  const high = vulnsArray.filter(v => (v.severity || '').toUpperCase() === 'HIGH').length;
  const med = vulnsArray.filter(v => (v.severity || '').toUpperCase() === 'MEDIUM').length;
  const low = vulnsArray.filter(v => (v.severity || '').toUpperCase() === 'LOW').length;
  const totalVulns = vulnsArray.length;
  
  let riskLevel = 'LOW';
  if (crit > 0) riskLevel = 'CRITICAL';
  else if (high > 0) riskLevel = 'HIGH';
  else if (med > 0) riskLevel = 'MEDIUM';

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          background: 'linear-gradient(145deg, rgba(17,25,40,0.97) 0%, rgba(12,17,29,0.99) 100%)',
          border: '1px solid rgba(0,212,255,0.12)',
          backdropFilter: 'blur(20px)',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pb: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Security sx={{ color: '#00D4FF', fontSize: 28 }} />
          <Box>
            <Typography variant="h6" fontWeight={700}>
              AI Pipeline Results
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {reportName}
            </Typography>
          </Box>
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ color: 'text.secondary' }}>
          <Close />
        </IconButton>
      </DialogTitle>

      <Tabs
        value={tabValue}
        onChange={(e, v) => setTabValue(v)}
        sx={{ px: 3, borderBottom: 1, borderColor: 'rgba(255,255,255,0.1)', mb: 1 }}
        textColor="inherit"
        indicatorColor="primary"
      >
        <Tab label="Overview" sx={{ color: '#fff', fontWeight: 600 }} />
        <Tab label="Full JSON" sx={{ color: '#fff', fontWeight: 600 }} />
        <Tab label="Vulnerabilities" sx={{ color: '#fff', fontWeight: 600 }} />
      </Tabs>

      <DialogContent sx={{ pt: 1, minHeight: 400 }}>
        {tabValue === 0 && (
          <Box>
        {/* ── Risk Score Card ── */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            mb: 3,
            flexWrap: 'wrap',
          }}
        >
          <Box
            sx={{
              flex: '1 1 200px',
              p: 2.5,
              borderRadius: 2.5,
              background: riskLevelGradient[riskLevel] || riskLevelGradient.MEDIUM,
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                top: -20,
                right: -20,
                width: 100,
                height: 100,
                borderRadius: '50%',
                background: 'rgba(255,255,255,0.1)',
              }}
            />
            <Typography variant="overline" sx={{ color: 'rgba(255,255,255,0.8)', fontWeight: 600 }}>
              Overall Risk Score
            </Typography>
            <Typography variant="h4" fontWeight={800} sx={{ color: '#fff', mt: 1 , background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>
              {execSummary.summary_text || riskLevel}
            </Typography>
            <Chip
              label={riskLevel}
              size="small"
              sx={{
                mt: 0.5,
                fontWeight: 700,
                backgroundColor: 'rgba(255,255,255,0.2)',
                color: '#fff',
                fontSize: '0.7rem',
              }}
            />
          </Box>

          <Box
            sx={{
              flex: '1 1 200px',
              p: 2.5,
              borderRadius: 2.5,
              background: 'rgba(0,212,255,0.06)',
              border: '1px solid rgba(0,212,255,0.1)',
            }}
          >
            <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 600 }}>
              Vulnerabilities Summary
            </Typography>
            <Typography variant="h3" fontWeight={800} sx={{ color: '#00D4FF' }}>
              {totalVulns}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
              {crit > 0 && (
                <Chip label={`${crit} Critical`} size="small" sx={{ fontSize: '0.65rem', fontWeight: 600, bgcolor: 'rgba(255,23,68,0.15)', color: '#FF1744' }} />
              )}
              {high > 0 && (
                <Chip label={`${high} High`} size="small" sx={{ fontSize: '0.65rem', fontWeight: 600, bgcolor: 'rgba(255,145,0,0.15)', color: '#FF9100' }} />
              )}
              {med > 0 && (
                <Chip label={`${med} Medium`} size="small" sx={{ fontSize: '0.65rem', fontWeight: 600, bgcolor: 'rgba(255,214,0,0.15)', color: '#FFD600' }} />
              )}
              {low > 0 && (
                <Chip label={`${low} Low`} size="small" sx={{ fontSize: '0.65rem', fontWeight: 600, bgcolor: 'rgba(0,230,118,0.15)', color: '#00E676' }} />
              )}
            </Box>
          </Box>
        </Box>

        {/* ── Vulnerabilities Details ── */}
        <Box sx={{ mb: 2 }}>
          <Box
            onClick={() => toggleSection('detailed_observations')}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              p: 1.5,
              borderRadius: 2,
              '&:hover': { bgcolor: 'rgba(0,212,255,0.04)' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <BugReport sx={{ color: '#FF9100', fontSize: 20 }} />
              <Typography variant="subtitle1" fontWeight={700}>
                Detailed Observations
              </Typography>
            </Box>
            {expandedSections.detailed_observations ? <ExpandLess /> : <ExpandMore />}
          </Box>
          <Collapse in={expandedSections.detailed_observations}>
            
            <Box sx={{ pl: 1, pr: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {(vulnsArray).map((v, i) => (
                <Box
                  key={v.finding_id || i}
                  sx={{
                    p: 2.5,
                    borderRadius: 3,
                    border: `1px solid ${severityColor[v.severity] || '#aaa'}40`,
                    bgcolor: 'rgba(0,0,0,0.2)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    position: 'relative',
                    overflow: 'hidden'
                  }}
                >
                  <Box sx={{ position: 'absolute', top: 0, left: 0, width: 4, height: '100%', bgcolor: severityColor[v.severity] || '#aaa' }} />
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5, pl: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                      <Typography variant="h6" fontWeight={700} sx={{ color: '#fff' }}>
                        {v.title}
                      </Typography>
                      <Chip label={v.severity} size="small" sx={{ fontWeight: 800, fontSize: '0.65rem', bgcolor: `${severityColor[v.severity] || '#aaa'}25`, color: severityColor[v.severity] || '#aaa', borderRadius: 1 }} />
                      {v.status && <Chip label={v.status} size="small" sx={{ fontWeight: 600, fontSize: '0.65rem', bgcolor: 'rgba(255,255,255,0.1)', color: '#ddd', borderRadius: 1 }} />}
                      {v.new_or_repeat && <Chip label={v.new_or_repeat} size="small" sx={{ fontWeight: 600, fontSize: '0.65rem', bgcolor: 'rgba(255,255,255,0.1)', color: '#ddd', borderRadius: 1 }} />}
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      {v.cvss_score && (
                        <Chip label={`CVSS: ${v.cvss_score}`} size="small" sx={{ fontWeight: 700, bgcolor: 'rgba(0,212,255,0.15)', color: '#00D4FF' }} />
                      )}
                      {v.reported_epss_score && (
                        <Chip label={`EPSS: ${v.reported_epss_score}`} size="small" sx={{ fontWeight: 700, bgcolor: 'rgba(156,39,176,0.15)', color: '#E1BEE7' }} />
                      )}
                    </Box>
                  </Box>

                  <Box sx={{ pl: 1 }}>
                    {v.finding_id && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5, fontFamily: 'monospace' }}>
                        ID: {v.finding_id}
                      </Typography>
                    )}
                    
                    <Typography variant="body2" sx={{ color: '#ccc', mb: 2, lineHeight: 1.6 }}>
                      {v.observation_description}
                    </Typography>

                    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 2, mb: 2, p: 2, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 2 }}>
                      {v.impact_level && (
                        <Box>
                          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">IMPACT LEVEL</Typography>
                          <Typography variant="body2" color="#fff">{v.impact_level}</Typography>
                        </Box>
                      )}
                      {v.likelihood_level && (
                        <Box>
                          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">LIKELIHOOD</Typography>
                          <Typography variant="body2" color="#fff">{v.likelihood_level}</Typography>
                        </Box>
                      )}
                      {v.cve_id && v.cve_id.length > 0 && (
                        <Box>
                          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">CVE IDs</Typography>
                          <Typography variant="body2" color="#fff" sx={{fontFamily: 'monospace'}}>{v.cve_id.join(', ')}</Typography>
                        </Box>
                      )}
                      {v.cwe && v.cwe.length > 0 && (
                        <Box>
                          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">CWE</Typography>
                          <Typography variant="body2" color="#fff" sx={{fontFamily: 'monospace'}}>{v.cwe.join(', ')}</Typography>
                        </Box>
                      )}
                      {v.affected_asset && v.affected_asset.length > 0 && (
                        <Box>
                          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">AFFECTED ASSETS</Typography>
                          <Typography variant="body2" color="#fff">{v.affected_asset.join(', ')}</Typography>
                        </Box>
                      )}
                      {v.cvss_vector && (
                        <Box sx={{ gridColumn: '1 / -1' }}>
                          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">CVSS VECTOR</Typography>
                          <Typography variant="body2" color="#fff" sx={{fontFamily: 'monospace'}}>{v.cvss_vector}</Typography>
                        </Box>
                      )}
                    </Box>

                    {v.severity_rationale && (
                      <Box sx={{ mb: 1.5 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" gutterBottom>SEVERITY RATIONALE</Typography>
                        <Typography variant="body2" color="#ccc">{v.severity_rationale}</Typography>
                      </Box>
                    )}
                    
                    {v.impact && (
                      <Box sx={{ mb: 1.5 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" gutterBottom>IMPACT</Typography>
                        <Typography variant="body2" color="#ccc">{v.impact}</Typography>
                      </Box>
                    )}

                    {v.likely_root_cause && (
                      <Box sx={{ mb: 1.5 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" gutterBottom>ROOT CAUSE</Typography>
                        <Typography variant="body2" color="#ccc">{v.likely_root_cause}</Typography>
                      </Box>
                    )}

                    {v.preconditions && (
                      <Box sx={{ mb: 1.5 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" gutterBottom>PRECONDITIONS</Typography>
                        <Typography variant="body2" color="#ccc">{v.preconditions}</Typography>
                      </Box>
                    )}

                    {v.recommendation && (
                      <Box sx={{ p: 1.5, bgcolor: 'rgba(0, 230, 118, 0.05)', borderLeft: '3px solid #00E676', borderRadius: '0 4px 4px 0', mt: 2 }}>
                        <Typography variant="caption" sx={{ color: '#00E676', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                          <TipsAndUpdates fontSize="small" /> RECOMMENDATION
                        </Typography>
                        <Typography variant="body2" color="#ddd">{v.recommendation}</Typography>
                      </Box>
                    )}
                  </Box>
                </Box>
              ))}
            </Box>

          </Collapse>
        </Box>

        <Divider sx={{ borderColor: 'rgba(255,255,255,0.04)', my: 1 }} />

        {/* ── Compliance Results ── */}
        <Box sx={{ mb: 2 }}>
          <Box
            onClick={() => toggleSection('compliance')}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              p: 1.5,
              borderRadius: 2,
              '&:hover': { bgcolor: 'rgba(0,212,255,0.04)' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Shield sx={{ color: '#00D4FF', fontSize: 20 }} />
              <Typography variant="subtitle1" fontWeight={700}>
                Compliance Results
              </Typography>
            </Box>
            {expandedSections.compliance ? <ExpandLess /> : <ExpandMore />}
          </Box>
          <Collapse in={expandedSections.compliance}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, p: 1 }}>
              {Object.entries(compliance).map(([framework, data]) => {
                const statusColorMap = {
                  COMPLIANT: '#00E676',
                  PARTIALLY_COMPLIANT: '#FFD600',
                  NON_COMPLIANT: '#FF1744',
                };
                const color = statusColorMap[data.status] || '#aaa';
                return (
                  <Box
                    key={framework}
                    sx={{
                      flex: '1 1 180px',
                      p: 2,
                      borderRadius: 2,
                      border: `1px solid ${color}22`,
                      bgcolor: `${color}06`,
                    }}
                  >
                    <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>
                      {framework}
                    </Typography>
                    <Chip
                      label={data.status.replace(/_/g, ' ')}
                      size="small"
                      sx={{
                        fontWeight: 600,
                        fontSize: '0.6rem',
                        bgcolor: `${color}18`,
                        color,
                        mb: 1,
                      }}
                    />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Score: <b>{data.score}</b>
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Gaps: <b>{data.gaps_identified}</b>
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={data.score}
                      sx={{
                        mt: 1,
                        height: 4,
                        borderRadius: 2,
                        bgcolor: `${color}10`,
                        '& .MuiLinearProgress-bar': {
                          borderRadius: 2,
                          bgcolor: color,
                        },
                      }}
                    />
                  </Box>
                );
              })}
            </Box>
          </Collapse>
        </Box>

        <Divider sx={{ borderColor: 'rgba(255,255,255,0.04)', my: 1 }} />

        {/* ── Recommendations ── */}
        <Box>
          <Box
            onClick={() => toggleSection('recommendations')}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              p: 1.5,
              borderRadius: 2,
              '&:hover': { bgcolor: 'rgba(0,212,255,0.04)' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TipsAndUpdates sx={{ color: '#FFD600', fontSize: 20 }} />
              <Typography variant="subtitle1" fontWeight={700}>
                Recommendations
              </Typography>
            </Box>
            {expandedSections.recommendations ? <ExpandLess /> : <ExpandMore />}
          </Box>
          <Collapse in={expandedSections.recommendations}>
            <Box sx={{ pl: 1, pr: 1 }}>
              {recommendations.map((rec, i) => (
                <Box
                  key={i}
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1.5,
                    p: 1.5,
                    mb: 0.5,
                    borderRadius: 2,
                    '&:hover': { bgcolor: 'rgba(255,214,0,0.04)' },
                  }}
                >
                  <Box
                    sx={{
                      minWidth: 24,
                      height: 24,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #FFD600, #FFAB00)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      color: '#000',
                      mt: 0.2,
                    }}
                  >
                    {i + 1}
                  </Box>
                  <Typography variant="body2">{rec}</Typography>
                </Box>
              ))}
            </Box>
          </Collapse>
        </Box>

        {/* ── Pipeline Metadata ── */}
        <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Typography variant="caption" color="text.secondary">
              Pipeline ID: <code>{results.pipeline_id}</code>
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Processed: {new Date(results.analysis_timestamp).toLocaleString()}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Duration: {results.processing_time_seconds}s
            </Typography>
          </Box>
        </Box>
        </Box>
        )}
        {tabValue === 1 && (
          <Box sx={{ p: 1, maxHeight: 600, overflowY: 'auto' }}>
            <JsonSectionView data={results} />
          </Box>
        )}

        {tabValue === 2 && (
          <Box sx={{ p: 2 }}>
             {vulnsArray.map((v) => (
                <Box key={v.finding_id} sx={{ mb: 2, p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
                   <Typography variant="subtitle2" color="primary">{v.title}</Typography>
                   <Typography variant="caption" color="text.secondary">Severity: {v.severity}</Typography>
                </Box>
             ))}
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* ──────────── Reports Page ──────────── */
function ReportsPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });
  const [search, setSearch] = useState('');
  const [searchDebounce, setSearchDebounce] = useState('');

  // Pipeline state
  const [pipelineStatus, setPipelineStatus] = useState({}); // { [reportId]: 'idle' | 'processing' | 'completed' | 'error' }
  const [pipelineResults, setPipelineResults] = useState({}); // { [reportId]: {...results} }
  const [confirmDialog, setConfirmDialog] = useState({ open: false, report: null });
  const [resultsDialog, setResultsDialog] = useState({ open: false, reportId: null, reportName: '' });

  useEffect(() => {
    const timer = setTimeout(() => setSearchDebounce(search), 400);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['reports', paginationModel.page, paginationModel.pageSize, searchDebounce],
    queryFn: async () => {
      const params = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
      };
      if (searchDebounce) params.search = searchDebounce;
      const response = await api.get('/api/reports', { params });
      return response.data;
    },
    keepPreviousData: true,
  });

  const reports = data?.reports || [];
  const total = data?.total || 0;

  const handleDownload = async (reportId, filename) => {
    try {
      const response = await api.get(`/api/reports/${reportId}/download`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      enqueueSnackbar('Download failed', { variant: 'error' });
    }
  };

  const handleDelete = async (reportId) => {
    if (!window.confirm('Are you sure you want to delete this report?')) return;
    try {
      await api.delete(`/api/reports/${reportId}`);
      enqueueSnackbar('Report deleted', { variant: 'success' });
      refetch();
    } catch {
      enqueueSnackbar('Delete failed', { variant: 'error' });
    }
  };

  /* ── Pipeline Handlers ── */
  const openConfirmDialog = (report) => {
    setConfirmDialog({ open: true, report });
  };

  const closeConfirmDialog = () => {
    setConfirmDialog({ open: false, report: null });
  };

  const handleRunPipeline = async () => {
    const report = confirmDialog.report;
    if (!report) return;
    closeConfirmDialog();

    const reportId = report.report_id;
    setPipelineStatus((prev) => ({ ...prev, [reportId]: 'processing' }));

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${api.defaults.baseURL || ''}/api/reports/${reportId}/run-pipeline`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) {
          const errText = await response.text();
          throw new Error(`Pipeline error: ${response.status} - ${errText}`);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalData = null;
      
      while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop();
          
          for (const line of lines) {
              if (line.startsWith('data: ')) {
                  try {
                      const event = JSON.parse(line.substring(6));
                      if (event.type === 'result') {
                          finalData = event.data;
                      } else if (event.type === 'error') {
                          throw new Error(event.message);
                      }
                  } catch (e) {
                      // ignore parse errors
                  }
              }
          }
      }
      
      setPipelineResults((prev) => ({ ...prev, [reportId]: finalData }));
      setPipelineStatus((prev) => ({ ...prev, [reportId]: 'completed' }));
      enqueueSnackbar('AI Pipeline completed successfully!', { variant: 'success' });
      refetch();
    } catch (err) {
      setPipelineStatus((prev) => ({ ...prev, [reportId]: 'error' }));
      const detail = err.response?.data?.detail || 'Pipeline failed';
      enqueueSnackbar(`Pipeline error: ${detail}`, { variant: 'error' });
    }
  };

  const openResultsDialog = (reportId, reportName) => {
    setResultsDialog({ open: true, reportId, reportName });
  };

  const closeResultsDialog = () => {
    setResultsDialog({ open: false, reportId: null, reportName: '' });
  };

  const handleViewResults = async (report) => {
    try {
      const response = await api.get(`/api/reports/${report.report_id}/results`);
      setPipelineResults((prev) => ({ ...prev, [report.report_id]: response.data }));
      setPipelineStatus((prev) => ({ ...prev, [report.report_id]: 'completed' }));
      openResultsDialog(report.report_id, report.original_filename);
    } catch (err) {
      if (err.response?.status === 404) {
        enqueueSnackbar('No pipeline results found for this report.', { variant: 'info' });
      } else {
        enqueueSnackbar('Failed to load results.', { variant: 'error' });
      }
    }
  };

  const renderPipelineChip = (report) => {
    const status = pipelineStatus[report.report_id];

    if (status === 'processing') {
      return (
        <Chip
          icon={<HourglassTop sx={{ fontSize: 14, animation: 'spin 1.5s linear infinite', '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } } }} />}
          label="Processing"
          size="small"
          sx={{
            fontWeight: 600,
            fontSize: '0.7rem',
            bgcolor: 'rgba(0,212,255,0.12)',
            color: '#00D4FF',
            border: '1px solid rgba(0,212,255,0.25)',
            animation: 'pulse 2s ease-in-out infinite',
            '@keyframes pulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.6 },
            },
          }}
        />
      );
    }

    if (status === 'completed' || report.has_pipeline_data) {
      return (
        <Chip
          icon={<CheckCircle sx={{ fontSize: 14 }} />}
          label="Completed"
          size="small"
          onClick={() => openResultsDialog(report.report_id, report.original_filename)}
          sx={{
            fontWeight: 600,
            fontSize: '0.7rem',
            bgcolor: 'rgba(0,230,118,0.12)',
            color: '#00E676',
            border: '1px solid rgba(0,230,118,0.25)',
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              bgcolor: 'rgba(0,230,118,0.2)',
              transform: 'scale(1.05)',
            },
          }}
        />
      );
    }

    if (status === 'error') {
      return (
        <Chip
          icon={<Warning sx={{ fontSize: 14 }} />}
          label="Failed"
          size="small"
          sx={{
            fontWeight: 600,
            fontSize: '0.7rem',
            bgcolor: 'rgba(255,23,68,0.12)',
            color: '#FF1744',
            border: '1px solid rgba(255,23,68,0.25)',
          }}
        />
      );
    }

    return (
      <Typography variant="caption" color="text.secondary">
        —
      </Typography>
    );
  };

  const columns = [
    {
      field: 'original_filename',
      headerName: 'File',
      flex: 1.5,
      renderCell: (params) => {
        const report = params.row;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}>
            <Typography fontSize="1.2rem">
              {extIcon[report.file_extension] || '📄'}
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: 200 }}>
                  {report.original_filename}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {report.file_extension.toUpperCase()}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', flexDirection: 'column', mt: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: '0.65rem' }}>
                  SHA256: {report.sha256_hash.substring(0, 16)}...
                </Typography>
                {report.simhash && (
                  <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: '0.65rem' }}>
                    SimHash: {report.simhash}
                  </Typography>
                )}
              </Box>
            </Box>
          </Box>
        );
      }
    },
    {
      field: 'agency',
      headerName: 'Agency',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          {params.row.agency?.agency_name || '—'}
        </Typography>
      )
    },
    {
      field: 'version',
      headerName: 'Version',
      width: 130,
      renderCell: (params) => {
        const report = params.row;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            {report.partial_duplicate ? (
              <Link
                to={`/reports/${report.partial_duplicate.original_report_id}`}
                style={{ textDecoration: 'none' }}
              >
                <Chip
                  label="Partial Duplicate"
                  size="small"
                  color="warning"
                  variant="outlined"
                  sx={{ cursor: 'pointer', fontWeight: 600, fontSize: '0.7rem' }}
                />
              </Link>
            ) : (
              <Chip
                label="Original"
                size="small"
                color="success"
                variant="outlined"
                sx={{ fontWeight: 600, fontSize: '0.7rem' }}
              />
            )}
          </Box>
        );
      }
    },
    {
      field: 'uploader_username',
      headerName: 'Uploader',
      width: 120,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          {params.value || '—'}
        </Typography>
      )
    },
    {
      field: 'file_size',
      headerName: 'Size',
      width: 100,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          {(params.value / 1024).toFixed(1)} KB
        </Typography>
      )
    },
    {
      field: 'upload_status',
      headerName: 'Status',
      width: 130,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          <Chip
            label={params.value}
            color={statusColor[params.value] || 'default'}
            size="small"
            sx={{ fontWeight: 600, fontSize: '0.7rem' }}
          />
        </Box>
      )
    },
    {
      field: 'pipeline',
      headerName: 'Pipeline',
      width: 130,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          {renderPipelineChip(params.row)}
        </Box>
      )
    },
    {
      field: 'created_at',
      headerName: 'Date',
      width: 120,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          {new Date(params.value).toLocaleDateString()}
        </Typography>
      )
    },
    {
      field: 'actions',
      headerName: 'Actions',
      flex: 1.5,
      sortable: false,
      renderCell: (params) => {
        const report = params.row;
        return (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', justifyContent: 'flex-end', height: '100%', width: '100%', pr: 1 }}>
            <Button
              size="small"
              variant="outlined"
              startIcon={<Security fontSize="small" />}
              onClick={() => handleViewResults(report)}
              sx={{ color: '#FFD600', borderColor: 'rgba(255,214,0,0.5)', '&:hover': { borderColor: '#FFD600', bgcolor: 'rgba(255,214,0,0.1)' }, textTransform: 'none', px: 1, py: 0.25, minWidth: 0 }}
            >
              Results
            </Button>
            <Button
              size="small"
              variant="outlined"
              startIcon={<Visibility fontSize="small" />}
              onClick={() => navigate(`/reports/${report.report_id}`)}
              sx={{ color: '#00D4FF', borderColor: 'rgba(0,212,255,0.5)', '&:hover': { borderColor: '#00D4FF', bgcolor: 'rgba(0,212,255,0.1)' }, textTransform: 'none', px: 1, py: 0.25, minWidth: 0 }}
            >
              View
            </Button>
            <Button
              size="small"
              variant="outlined"
              startIcon={<Download fontSize="small" />}
              onClick={() => handleDownload(report.report_id, report.original_filename)}
              sx={{ color: '#00E676', borderColor: 'rgba(0,230,118,0.5)', '&:hover': { borderColor: '#00E676', bgcolor: 'rgba(0,230,118,0.1)' }, textTransform: 'none', px: 1, py: 0.25, minWidth: 0 }}
            >
              Down
            </Button>
            {isAdmin() && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<Delete fontSize="small" />}
                onClick={() => handleDelete(report.report_id)}
                sx={{ color: '#FF1744', borderColor: 'rgba(255,23,68,0.5)', '&:hover': { borderColor: '#FF1744', bgcolor: 'rgba(255,23,68,0.1)' }, textTransform: 'none', px: 1, py: 0.25, minWidth: 0 }}
              >
                Del
              </Button>
            )}
          </Box>
        );
      }
    }
  ];

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ mb: 0.5 }}>
            Reports
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {total} reports in total
          </Typography>
        </Box>
      </Box>

      {/* Search */}
      <TextField
        id="reports-search"
        placeholder="Search reports by filename..."
        size="small"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 3, width: { xs: '100%', sm: 360 } }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <Search sx={{ color: 'text.secondary' }} />
            </InputAdornment>
          ),
        }}
      />

      <Card className="fade-in-up" sx={{ flexGrow: 1 }}>
        <CardContent sx={{ p: 0 }}>
          <Box sx={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={reports}
            columns={columns}
            getRowId={(row) => row.report_id}
            rowCount={total}
            loading={isLoading}
            paginationMode="server"
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            pageSizeOptions={[5, 10, 25, 50]}
            disableRowSelectionOnClick
            rowHeight={80}
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
                  <Description sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                  <Typography color="text.secondary">No reports found</Typography>
                </Box>
              ),
            }}
          />
          </Box>
        </CardContent>
      </Card>

      {/* ── Confirmation Dialog ── */}
      <Dialog
        open={confirmDialog.open}
        onClose={closeConfirmDialog}
        PaperProps={{
          sx: {
            borderRadius: 3,
            background: 'linear-gradient(145deg, rgba(17,25,40,0.97) 0%, rgba(12,17,29,0.99) 100%)',
            border: '1px solid rgba(0,212,255,0.12)',
            backdropFilter: 'blur(20px)',
            minWidth: 400,
          },
        }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <RocketLaunch sx={{ color: '#AB47BC' }} />
          <Typography variant="h6" fontWeight={700}>
            Run AI Pipeline
          </Typography>
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ color: 'text.secondary', mb: 2 }}>
            Are you sure you want to run the AI analysis pipeline on this report?
          </DialogContentText>
          {confirmDialog.report && (
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                bgcolor: 'rgba(0,212,255,0.04)',
                border: '1px solid rgba(0,212,255,0.08)',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Description sx={{ color: '#00D4FF', fontSize: 20 }} />
                <Typography variant="body2" fontWeight={600}>
                  {confirmDialog.report.original_filename}
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                Report ID: <code>{confirmDialog.report.report_id}</code>
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                Size: {(confirmDialog.report.file_size / 1024).toFixed(1)} KB • {confirmDialog.report.file_extension.toUpperCase()}
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button
            onClick={closeConfirmDialog}
            sx={{ color: 'text.secondary', fontWeight: 600 }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleRunPipeline}
            variant="contained"
            startIcon={<RocketLaunch />}
            sx={{
              background: 'linear-gradient(135deg, #AB47BC, #7B1FA2)',
              fontWeight: 700,
              px: 3,
              '&:hover': {
                background: 'linear-gradient(135deg, #CE93D8, #AB47BC)',
              },
            }}
          >
            Run Pipeline
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Results Dialog ── */}
      <PipelineResultsDialog
        open={resultsDialog.open}
        onClose={closeResultsDialog}
        results={pipelineResults[resultsDialog.reportId]}
        reportName={resultsDialog.reportName}
      />
    </Box>
  );
}

export default ReportsPage;

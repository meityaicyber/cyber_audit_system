import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box, Card, CardContent, Typography, LinearProgress, Alert, Chip, Paper, Button, Dialog, DialogTitle, DialogContent, DialogContentText, TextField, DialogActions, FormControl, InputLabel, Select, MenuItem, Tabs, Tab, RadioGroup, FormControlLabel, Radio, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, CircularProgress, Backdrop
} from '@mui/material';
import {
  CloudUpload, CheckCircle, Error as ErrorIcon, Description, Lock as LockIcon, PlayArrow, Folder, TableChart, Autorenew, Pending, Cancel, Download
} from '@mui/icons-material';
import { useSnackbar } from 'notistack';
import api from '../api/axios';
import * as XLSX from 'xlsx';
import { useBulkUpload } from '../contexts/BulkUploadContext';

function UploadReportPage() {
  // Cache buster: v4-folder-loading
  const { enqueueSnackbar } = useSnackbar();
  
  // Shared state
  const [tabValue, setTabValue] = useState(0);
  const [agencies, setAgencies] = useState([]);
  const [selectedAgency, setSelectedAgency] = useState('');

  // Single Upload state
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [pendingFile, setPendingFile] = useState(null);
  const [pipelineLog, setPipelineLog] = useState('');

  // Bulk Upload state
  const [excelFile, setExcelFile] = useState(null);
  const [pdfFiles, setPdfFiles] = useState([]);
  const [batchMode, setBatchMode] = useState('sequential');
  
  // Use global context for bulk tracking
  const {
      bulkFilesData, setBulkFilesData, bulkProgress, bulkTotal, bulkRunning, bulkFinished, setBulkFinished,
      bulkStartTime, bulkEndTime, bulkPaused, etaSeconds,
      startBulkUpload, pauseBulkUpload, resumeBulkUpload, resetBulkState
    } = useBulkUpload();
  const [generatingExcel, setGeneratingExcel] = useState(false);
  const [generatedExcelUrl, setGeneratedExcelUrl] = useState(null);
  const [folderLoading, setFolderLoading] = useState(false);
  const [extractedPasswords, setExtractedPasswords] = useState([]);
  const [txtFileNames, setTxtFileNames] = useState([]);

  useEffect(() => {
    const fetchAgencies = async () => {
      try {
        const response = await api.get('/api/agencies', { params: { limit: 100 } });
        setAgencies(response.data.agencies || []);
      } catch (err) {
        enqueueSnackbar('Failed to load agencies', { variant: 'error' });
      }
    };
    fetchAgencies();
  }, [enqueueSnackbar]);

  // SINGLE UPLOAD (Keep existing logic unchanged...)
  const onDrop = useCallback(
    async (acceptedFiles) => {
      if (acceptedFiles.length === 0) return;
      const file = acceptedFiles[0];
      setError(''); setResult(null); setUploading(true); setProgress(0);

      const formData = new FormData();
      formData.append('file', file);
      if (selectedAgency) formData.append('agency_id', selectedAgency);

      try {
        let reportId = null;
        try {
          const response = await api.post('/api/reports/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (e) => setProgress(Math.round((e.loaded * 100) / (e.total || 1))),
          });
          reportId = response.data.report_id;
          setResult(response.data); // Optimistically set result
          enqueueSnackbar('File uploaded successfully! Running AI pipeline...', { variant: 'info' });
          setPipelineLog('Starting AI pipeline...');
          
          const token = localStorage.getItem('access_token');
          const streamRes = await fetch(`${api.defaults.baseURL || ''}/api/reports/${reportId}/run-pipeline`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (!streamRes.ok) {
            const errText = await streamRes.text();
            throw new Error(`Pipeline error: ${streamRes.status} - ${errText}`);
          }
          const reader = streamRes.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
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
                        if (event.type === 'log') {
                            setPipelineLog(event.message);
                        } else if (event.type === 'error') {
                            throw new Error(event.message);
                        }
                    } catch (e) {}
                }
            }
          }
          setPipelineLog('');
          enqueueSnackbar('AI Pipeline completed successfully!', { variant: 'success' });
        } catch (err) {
          let msg = 'Operation failed';
          if (err.response) {
            if (err.response.data && typeof err.response.data.detail === 'string') {
              msg = err.response.data.detail;
            } else if (err.response.data && Array.isArray(err.response.data.detail)) {
              msg = err.response.data.detail.map(d => d.msg).join(', ');
            } else if (err.response.status === 413) {
              msg = "File size limit exceeded";
            } else if (err.response.status === 500) {
              msg = "Internal server error on backend";
            } else {
              msg = `Request failed with status code ${err.response.status}`;
            }
          } else {
            msg = err.message || 'Network error';
          }
          if (msg === 'PASSWORD_REQUIRED') {
            throw err; // Let outer catch handle password required
          }
          if (reportId) {
            enqueueSnackbar(`Pipeline failed: ${msg}. Rolling back...`, { variant: 'error' });
            try {
              await api.delete(`/api/reports/${reportId}`);
              setError(`${msg}. File deleted from system.`);
            } catch (rollbackErr) {
              setError(`${msg}. Rollback failed.`);
            }
            setResult(null); // Clear result since it failed
          } else {
            setError(msg);
            enqueueSnackbar(msg, { variant: 'error' });
          }
        }
      } catch (err) {
        let msg = 'Operation failed';
          if (err.response) {
            if (err.response.data && typeof err.response.data.detail === 'string') {
              msg = err.response.data.detail;
            } else if (err.response.data && Array.isArray(err.response.data.detail)) {
              msg = err.response.data.detail.map(d => d.msg).join(', ');
            } else if (err.response.status === 413) {
              msg = "File size limit exceeded";
            } else if (err.response.status === 500) {
              msg = "Internal server error on backend";
            } else {
              msg = `Request failed with status code ${err.response.status}`;
            }
          } else {
            msg = err.message || 'Network error';
          }
        if (msg === 'PASSWORD_REQUIRED') {
          setPasswordRequired(true); setPendingFile(file);
        } else {
          setError(msg || 'Upload failed. Please try again.');
          enqueueSnackbar(msg || 'Upload failed', { variant: 'error' });
        }
      } finally {
        setUploading(false);
        setPipelineLog('');
      }
    }, [enqueueSnackbar, selectedAgency]
  );

  const handlePasswordSubmit = async () => {
    if (!passwordInput || !pendingFile) return;
    setError(''); setUploading(true); setProgress(0);
    const formData = new FormData();
    formData.append('file', pendingFile);
    formData.append('file_password', passwordInput);
    if (selectedAgency) formData.append('agency_id', selectedAgency);

    try {
      let reportId = null;
      try {
        const response = await api.post('/api/reports/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (e) => setProgress(Math.round((e.loaded * 100) / (e.total || 1))),
        });
        reportId = response.data.report_id;
        setResult(response.data);
        enqueueSnackbar('File unlocked and uploaded successfully! Running AI pipeline...', { variant: 'info' });
        setPasswordRequired(false); setPasswordInput(''); setPendingFile(null);
        setPipelineLog('Starting AI pipeline...');
        
        const token = localStorage.getItem('access_token');
        const streamRes = await fetch(`${api.defaults.baseURL || ''}/api/reports/${reportId}/run-pipeline`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!streamRes.ok) {
          const errText = await streamRes.text();
          throw new Error(`Pipeline error: ${streamRes.status} - ${errText}`);
        }
        const reader = streamRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
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
                      if (event.type === 'log') {
                          setPipelineLog(event.message);
                      } else if (event.type === 'error') {
                          throw new Error(event.message);
                      }
                  } catch (e) {}
              }
          }
        }
        setPipelineLog('');
        enqueueSnackbar('AI Pipeline completed successfully!', { variant: 'success' });
      } catch (err) {
        let msg = 'Operation failed';
          if (err.response) {
            if (err.response.data && typeof err.response.data.detail === 'string') {
              msg = err.response.data.detail;
            } else if (err.response.data && Array.isArray(err.response.data.detail)) {
              msg = err.response.data.detail.map(d => d.msg).join(', ');
            } else if (err.response.status === 413) {
              msg = "File size limit exceeded";
            } else if (err.response.status === 500) {
              msg = "Internal server error on backend";
            } else {
              msg = `Request failed with status code ${err.response.status}`;
            }
          } else {
            msg = err.message || 'Network error';
          }
        if (msg === 'INVALID_PASSWORD') {
          throw err;
        }
        if (reportId) {
          enqueueSnackbar(`Pipeline failed: ${msg}. Rolling back...`, { variant: 'error' });
          try {
            await api.delete(`/api/reports/${reportId}`);
            setError(`${msg}. File deleted from system.`);
          } catch (rollbackErr) {
            setError(`${msg}. Rollback failed.`);
          }
          setResult(null);
        } else {
          setError(msg);
          enqueueSnackbar(msg, { variant: 'error' });
          setPasswordRequired(false); setPasswordInput(''); setPendingFile(null);
        }
      }
    } catch (err) {
      let msg = 'Operation failed';
          if (err.response) {
            if (err.response.data && typeof err.response.data.detail === 'string') {
              msg = err.response.data.detail;
            } else if (err.response.data && Array.isArray(err.response.data.detail)) {
              msg = err.response.data.detail.map(d => d.msg).join(', ');
            } else if (err.response.status === 413) {
              msg = "File size limit exceeded";
            } else if (err.response.status === 500) {
              msg = "Internal server error on backend";
            } else {
              msg = `Request failed with status code ${err.response.status}`;
            }
          } else {
            msg = err.message || 'Network error';
          }
      if (msg === 'INVALID_PASSWORD') {
        setError('Incorrect password. Please try again.');
      } else {
        setError(msg || 'Upload failed. Please try again.');
        setPasswordRequired(false); setPasswordInput(''); setPendingFile(null);
      }
    } finally {
      setUploading(false);
      setPipelineLog('');
    }
  };

  const handlePasswordCancel = () => {
    setPasswordRequired(false); setPasswordInput(''); setPendingFile(null);
    setError('Upload cancelled due to missing password.');
  };

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop, accept: { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] },
    maxFiles: 1, maxSize: 500 * 1024 * 1024, disabled: uploading,
  });

  const handleReset = () => { setResult(null); setError(''); setProgress(0); };

  const checkIsProtected = async (file) => {
    try {
      const lowerName = file.name.toLowerCase();
      if (lowerName.endsWith('.pdf')) {
        let buffer = await file.slice(0, 1024 * 10).arrayBuffer();
        let text = new TextDecoder('utf-8').decode(buffer);
        if (text.includes('/Encrypt')) return true;
        
        const endStart = Math.max(0, file.size - 1024 * 10);
        buffer = await file.slice(endStart, file.size).arrayBuffer();
        text = new TextDecoder('utf-8').decode(buffer);
        return text.includes('/Encrypt');
      } else if (lowerName.endsWith('.docx') || lowerName.endsWith('.doc')) {
        const buffer = await file.slice(0, 8).arrayBuffer();
        const bytes = new Uint8Array(buffer);
        const signature = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];
        if (bytes.length >= 8 && signature.every((val, i) => val === bytes[i])) {
          return true;
        }
      }
    } catch (e) {
      console.error("Failed to check file protection", e);
    }
    return false;
  };

  const processSelectedFiles = async (filesArrayRaw) => {
    setFolderLoading(true);
    // Yield to let UI update
    await new Promise(r => setTimeout(r, 150));

    const pdfDocFiles = [];
    const txtFiles = [];

    for (const f of filesArrayRaw) {
      const lowerName = f.name.toLowerCase();
      if (lowerName.endsWith('.pdf') || lowerName.endsWith('.docx') || lowerName.endsWith('.doc')) {
        pdfDocFiles.push(f);
      } else if (lowerName.endsWith('.txt')) {
        txtFiles.push(f);
      }
    }

    setTxtFileNames(txtFiles.map(f => f.name));
    setPdfFiles(pdfDocFiles);

    const initialData = await Promise.all(pdfDocFiles.map(async (f, i) => {
      const cleanName = (f.path || f.webkitRelativePath || f.name).split('/').pop().split('\\').pop();
      const isProtected = await checkIsProtected(f);
      return {
        id: i,
        file: f,
        name: cleanName,
        status: 'Pending',
        details: '-',
        protected: isProtected ? 'Yes' : 'No'
      };
    }));

    setBulkFilesData(initialData);

    // Read passwords from txt files
    const newPasswords = new Set();
    for (const txtFile of txtFiles) {
      try {
        const text = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve(e.target.result);
          reader.onerror = (e) => reject(e);
          reader.readAsText(txtFile);
        });
        const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l);
        lines.forEach(l => newPasswords.add(l));
      } catch (err) {
        console.error("Failed to read txt file", err);
      }
    }
    
    setExtractedPasswords(Array.from(newPasswords));
    setBulkFinished(false);
    setFolderLoading(false);
  };

  const onBulkDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles && acceptedFiles.length > 0) {
      processSelectedFiles(acceptedFiles);
    }
  }, [setBulkFilesData, setBulkFinished]);

  const { getRootProps: getBulkRootProps, getInputProps: getBulkInputProps, isDragActive: isBulkDragActive } = useDropzone({
    onDrop: onBulkDrop,
    disabled: bulkRunning || folderLoading,
  });

  const handleFolderSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const rawFiles = Array.from(e.target.files);
      const targetInput = e.target;
      processSelectedFiles(rawFiles).finally(() => {
        targetInput.value = null;
      });
    } else {
      setFolderLoading(false);
      if (e.target) e.target.value = null;
    }
  };

  const handleGenerateMapping = async (e) => {
    if (!e.target.files || e.target.files.length === 0) return;
    setGeneratingExcel(true);
    
    try {
      const files = Array.from(e.target.files);
      
      // Group files by their directory
      const directories = {};
      files.forEach(f => {
        const pathParts = (f.webkitRelativePath || f.name).split('/');
        pathParts.pop(); // remove filename
        const dirPath = pathParts.join('/');
        if (!directories[dirPath]) directories[dirPath] = [];
        directories[dirPath].push(f);
      });

      const mappingData = [];

      for (const dir in directories) {
        const dirFiles = directories[dir];
        const txtFiles = dirFiles.filter(f => f.name.toLowerCase().endsWith('.txt'));
        const reportFiles = dirFiles.filter(f => f.name.toLowerCase().endsWith('.pdf') || f.name.toLowerCase().endsWith('.docx'));

        if (txtFiles.length > 0 && reportFiles.length > 0) {
          // Read the first txt file as password
          const txtFile = txtFiles[0];
          const text = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsText(txtFile);
          });
          
          const password = text.trim();
          
          if (password) {
            reportFiles.forEach(rf => {
               mappingData.push({
                 "File Name": rf.name.substring(0, rf.name.lastIndexOf('.')) || rf.name,
                 "Password": password
               });
            });
          }
        }
      }

      if (mappingData.length === 0) {
        enqueueSnackbar('No valid password text files found in the folder structure.', { variant: 'warning' });
        setGeneratingExcel(false);
        return;
      }

      // Create Excel
      const worksheet = XLSX.utils.json_to_sheet(mappingData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Mapping");
      
      // Generate binary string
      const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      
      // Create download URL
      const url = URL.createObjectURL(blob);
      setGeneratedExcelUrl(url);
      
      // Auto-set as excel file
      const generatedFile = new File([blob], 'generated_mapping.xlsx', { type: blob.type });
      setExcelFile(generatedFile);
      
      enqueueSnackbar(`Generated mapping for ${mappingData.length} files successfully!`, { variant: 'success' });
    } catch (error) {
      console.error('Error generating mapping:', error);
      enqueueSnackbar('Failed to generate Excel mapping', { variant: 'error' });
    } finally {
      setGeneratingExcel(false);
      // Clear input so it can be clicked again
      e.target.value = null;
    }
  };

  const handleBulkLaunch = async () => {
    if (pdfFiles.length === 0) {
      enqueueSnackbar('Please select a folder with valid files first', {variant: 'warning'});
      return;
    }

    let passwordMap = {};
    if (excelFile) {
      try {
        const data = await excelFile.arrayBuffer();
        const workbook = XLSX.read(data);
        const sheetName = workbook.SheetNames[0];
        const sheet = workbook.Sheets[sheetName];
        const rows = XLSX.utils.sheet_to_json(sheet);
        
        rows.forEach(row => {
          const auditKey = Object.keys(row).find(k => {
            const low = k.toLowerCase();
            return low.includes('audit') || low.includes('no') || low.includes('id') || low.includes('unique') || low.includes('file');
          });
          const passKey = Object.keys(row).find(k => {
            const low = k.toLowerCase();
            return low.includes('pass') || low.includes('pwd');
          });
          
          if (auditKey && row[auditKey]) {
            passwordMap[String(row[auditKey]).toLowerCase()] = passKey ? row[passKey] : '';
          }
        });
      } catch (err) {
        enqueueSnackbar('Failed to parse Excel file', {variant: 'error'});
        return;
      }
    }

    const concurrency = batchMode === 'batch8' ? 8 : (batchMode === 'batch4' ? 4 : (batchMode === 'batch2' ? 2 : 1));
    
    // Call the context function
    startBulkUpload(bulkFilesData, passwordMap, selectedAgency, concurrency, extractedPasswords);
    setPdfFiles([]); // Free memory!
  };

  const renderStatusChip = (status) => {
    switch (status) {
      case 'Pending': return <Chip size="small" icon={<Pending />} label="Pending" color="default" />;
      case 'Uploading': return <Chip size="small" icon={<Autorenew sx={{ animation: 'spin 2s linear infinite', '@keyframes spin': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } } }} />} label="Uploading" color="info" />;
      case 'Pipeline': return <Chip size="small" icon={<Autorenew sx={{ animation: 'spin 2s linear infinite', '@keyframes spin': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } } }} />} label="Pipeline Running" color="primary" />;
      case 'Success': return <Chip size="small" icon={<CheckCircle />} label="Success" color="success" />;
      case 'Failed': return <Chip size="small" icon={<Cancel />} label="Failed" color="error" />;
      default: return <Chip size="small" label={status} />;
    }
  };

  const renderFinalReport = () => {
    if (!bulkFinished) return null;
    
    const successCount = bulkFilesData.filter(f => f.status === 'Success').length;
    const failedCount = bulkFilesData.filter(f => f.status === 'Failed').length;
    const timeTaken = bulkEndTime && bulkStartTime ? ((bulkEndTime - bulkStartTime) / 1000).toFixed(1) : 0;

    return (
      <Paper elevation={0} sx={{ mt: 4, p: 3, borderRadius: 2, background: 'rgba(0, 212, 255, 0.05)', border: '1px solid rgba(0, 212, 255, 0.2)' }}>
        <Typography variant="h6" fontWeight={700} gutterBottom sx={{ color: '#00D4FF', display: 'flex', alignItems: 'center', gap: 1 }}>
          <CheckCircle /> Bulk Processing Report
        </Typography>
        <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mt: 2 }}>
          <Box>
            <Typography variant="body2" color="text.secondary" fontWeight={600}>Total Files</Typography>
            <Typography variant="h4" fontWeight={700} sx={{ background: '-webkit-linear-gradient(45deg, #00D4FF, #00E676)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{bulkTotal}</Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary" fontWeight={600}>Successful</Typography>
            <Typography variant="h4" fontWeight={700} color="success.main">{successCount}</Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary" fontWeight={600}>Failed</Typography>
            <Typography variant="h4" fontWeight={700} color="error.main">{failedCount}</Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary" fontWeight={600}>Time Taken</Typography>
            <Typography variant="h4" fontWeight={700}>{timeTaken}s</Typography>
          </Box>
        </Box>
      </Paper>
    );
  };

  return (
    <Box>
      <Typography variant="h4" fontWeight={800} sx={{ mb: 1 }}>
        Upload Reports
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        Upload single or bulk PDF or DOCX files for processing and validation
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 4 }}>
        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab label="Single Upload" />
          <Tab label="Bulk Upload" />
        </Tabs>
      </Box>

      {/* Common Agency Select */}
      <Box sx={{ mb: 4, maxWidth: 400 }}>
        <FormControl fullWidth variant="outlined">
          <InputLabel id="agency-select-label">Select Agency (Optional)</InputLabel>
          <Select
            labelId="agency-select-label"
            value={selectedAgency}
            onChange={(e) => setSelectedAgency(e.target.value)}
            label="Select Agency (Optional)"
            disabled={uploading || bulkRunning}
          >
            <MenuItem value=""><em>None</em></MenuItem>
            {agencies.map((agency) => (
              <MenuItem key={agency.agency_id} value={agency.agency_id}>
                {agency.agency_name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* --- SINGLE UPLOAD TAB --- */}
      {tabValue === 0 && (
        <Card className="fade-in-up">
           {/* Same contents as before... */}
           <CardContent sx={{ p: 4 }}>
            <Paper {...getRootProps()} elevation={0} sx={{
                p: 6, textAlign: 'center', cursor: uploading ? 'not-allowed' : 'pointer',
                borderRadius: 3, border: '2px dashed', borderColor: isDragActive ? '#00D4FF' : isDragReject ? '#FF1744' : 'rgba(255,255,255,0.12)',
                background: isDragActive ? 'rgba(0, 212, 255, 0.05)' : 'rgba(0, 0, 0, 0.15)', transition: 'all 0.3s ease',
                '&:hover': { borderColor: 'rgba(0, 212, 255, 0.4)', background: 'rgba(0, 212, 255, 0.03)' },
              }}>
              <input {...getInputProps()} />
              <CloudUpload sx={{ fontSize: 64, color: isDragActive ? '#00D4FF' : 'text.secondary', mb: 2, filter: isDragActive ? 'drop-shadow(0 0 12px rgba(0,212,255,0.5))' : 'none' }} />
              <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>{isDragActive ? 'Drop the file here' : 'Drag & drop a file here, or click to browse'}</Typography>
              <Typography variant="body2" color="text.secondary">Supported formats: PDF, DOCX — Max size: 500MB</Typography>
            </Paper>

            {uploading && (
              <Box sx={{ mt: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2" fontWeight={500}>
                    {progress < 100 ? 'Uploading...' : 'Running in pipeline...'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {progress < 100 ? `${progress}%` : 'Processing'}
                  </Typography>
                </Box>
                <LinearProgress 
                  variant={progress < 100 ? "determinate" : "indeterminate"} 
                  value={progress < 100 ? progress : undefined} 
                  sx={{ height: 8, borderRadius: 4, backgroundColor: 'rgba(0, 212, 255, 0.1)', '& .MuiLinearProgress-bar': { background: 'linear-gradient(90deg, #00D4FF, #00E676)' } }} 
                />
                {pipelineLog && (
                  <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary', fontStyle: 'italic' }}>
                    {pipelineLog}
                  </Typography>
                )}
              </Box>
            )}

            {error && <Alert severity="error" sx={{ mt: 3, borderRadius: 2 }} icon={<ErrorIcon />}>{error}</Alert>}

            {result && (
              <Box sx={{ mt: 3 }}>
                <Alert severity={result.duplicate_status === 'PARTIAL_DUPLICATE' ? 'warning' : 'success'} sx={{ mb: 3, borderRadius: 2 }} icon={result.duplicate_status === 'PARTIAL_DUPLICATE' ? <ErrorIcon /> : <CheckCircle />}>
                  {result.message}
                </Alert>
                <Paper elevation={0} sx={{ p: 3, borderRadius: 2, background: 'rgba(0, 230, 118, 0.05)', border: '1px solid rgba(0, 230, 118, 0.15)' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                    <Description sx={{ color: '#00E676', fontSize: 32 }} />
                    <Box>
                      <Typography variant="body1" fontWeight={600}>{result.original_filename}</Typography>
                      <Typography variant="caption" color="text.secondary">{(result.file_size / 1024).toFixed(1)} KB</Typography>
                    </Box>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Chip label={`Status: ${result.upload_status}`} color="success" size="small" sx={{ fontWeight: 600 }} />
                    <Chip label={`Validation: ${result.validation_status}`} color="success" size="small" sx={{ fontWeight: 600 }} />
                  </Box>
                </Paper>
                <Button variant="outlined" onClick={handleReset} sx={{ mt: 2 }}>Upload Another File</Button>
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* --- BULK UPLOAD TAB --- */}
      {tabValue === 1 && (
        <Card className="fade-in-up">
          <CardContent sx={{ p: 4 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              
              <Box>
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  1. Excel Mapping (Optional)
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Upload an Excel file containing audit numbers and passwords.
                </Typography>
                
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Button variant="outlined" component="label" startIcon={<TableChart />}>
                    {excelFile ? excelFile.name : 'Select Excel File'}
                    <input type="file" accept=".xlsx, .xls, .csv" hidden onChange={(e) => setExcelFile(e.target.files[0])} disabled={bulkRunning} />
                  </Button>
                  <Typography variant="body2" color="text.secondary">OR</Typography>
                  <Button variant="contained" component="label" color="secondary" startIcon={generatingExcel ? <Autorenew sx={{ animation: 'spin 2s linear infinite', '@keyframes spin': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } } }} /> : <Autorenew />} disabled={bulkRunning || generatingExcel}>
                    {generatingExcel ? 'Generating...' : 'Auto-Generate from Folder'}
                    <input type="file" webkitdirectory="true" directory="true" multiple hidden onChange={handleGenerateMapping} disabled={bulkRunning || generatingExcel} />
                  </Button>
                  {generatedExcelUrl && (
                    <Button variant="text" color="info" startIcon={<Download />} component="a" href={generatedExcelUrl} download="mapping.xlsx">
                      Download Generated Excel
                    </Button>
                  )}
                </Box>

              </Box>

              <Box>
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  2. Select Report Folder or Files
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Select a folder or files containing the bulk PDF/Word reports. You can also drag and drop them here.
                </Typography>
                
                <Box
                  {...getBulkRootProps()}
                  sx={{
                    border: '2px dashed',
                    borderColor: isBulkDragActive ? 'primary.main' : 'rgba(255,255,255,0.2)',
                    borderRadius: 2,
                    p: 4,
                    textAlign: 'center',
                    bgcolor: isBulkDragActive ? 'rgba(0, 212, 255, 0.05)' : 'transparent',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: 'rgba(0, 212, 255, 0.02)'
                    }
                  }}
                >
                  <input {...getBulkInputProps()} />
                  <CloudUpload sx={{ fontSize: 48, color: isBulkDragActive ? 'primary.main' : 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" gutterBottom>
                    {isBulkDragActive ? 'Drop files/folders here' : 'Drag & Drop files/folders here'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    or use the buttons below
                  </Typography>
                  
                  <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }} onClick={e => e.stopPropagation()}>
                    <Button variant="outlined" component="label" startIcon={folderLoading ? <CircularProgress size={18} color="inherit" /> : <Folder />} disabled={bulkRunning || folderLoading}>
                      {folderLoading ? 'Reading Files...' : 'Select Folder'}
                      <input type="file" webkitdirectory="true" directory="true" multiple hidden onChange={handleFolderSelect} disabled={bulkRunning || folderLoading} />
                    </Button>
                    <Button variant="outlined" component="label" startIcon={folderLoading ? <CircularProgress size={18} color="inherit" /> : <Description />} disabled={bulkRunning || folderLoading}>
                      {folderLoading ? 'Reading Files...' : 'Select Files'}
                      <input type="file" multiple hidden accept=".pdf,.doc,.docx" onChange={handleFolderSelect} disabled={bulkRunning || folderLoading} />
                    </Button>
                  </Box>
                </Box>

                {folderLoading && (
                  <Paper elevation={0} sx={{ mt: 2, p: 3, borderRadius: 2, background: 'rgba(0, 212, 255, 0.05)', border: '1px solid rgba(0, 212, 255, 0.15)', display: 'flex', alignItems: 'center', gap: 2 }}>
                    <CircularProgress size={28} sx={{ color: '#00D4FF' }} />
                    <Box>
                      <Typography variant="body1" fontWeight={600} sx={{ color: '#00D4FF' }}>
                        Loading your files, please wait...
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Thank you for your patience. We are reading and preparing your files for upload. This may take a moment for large folders.
                      </Typography>
                    </Box>
                  </Paper>
                )}
                {!folderLoading && pdfFiles.length > 0 && (
                  <Typography variant="body2" color="success.main" sx={{ mt: 1 }}>
                    {pdfFiles.length} valid files found.
                  </Typography>
                )}
                {!folderLoading && txtFileNames.length > 0 && (
                  <Alert severity="info" sx={{ mt: 2, borderRadius: 2 }}>
                    Detected Text File(s): <strong>{txtFileNames.join(', ')}</strong> (Passwords loaded)
                  </Alert>
                )}
              </Box>

              <Box>
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  3. Batch Processing Mode
                </Typography>
                <FormControl component="fieldset" disabled={bulkRunning}>
                  <RadioGroup row value={batchMode} onChange={(e) => setBatchMode(e.target.value)}>
                    <FormControlLabel value="sequential" control={<Radio />} label="Sequential (1 by 1)" />
                    <FormControlLabel value="batch2" control={<Radio />} label="Batch of 2" />
                    <FormControlLabel value="batch4" control={<Radio />} label="Batch of 4" />
                    <FormControlLabel value="batch8" control={<Radio />} label="Batch of 8" />
                  </RadioGroup>
                </FormControl>
              </Box>

              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                  <Button variant="contained" color="primary" size="large" startIcon={<PlayArrow />} onClick={handleBulkLaunch} disabled={bulkRunning || pdfFiles.length === 0}>
                    {bulkRunning && !bulkPaused ? 'Running...' : 'Launch Bulk Processing'}
                  </Button>
                  
                  {bulkRunning && !bulkFinished && !bulkPaused && (
                    <Button variant="contained" color="warning" size="large" onClick={pauseBulkUpload}>
                      Pause Queue
                    </Button>
                  )}
                  {bulkPaused && !bulkFinished && (
                    <Button variant="contained" color="success" size="large" onClick={resumeBulkUpload}>
                      Resume Queue
                    </Button>
                  )}
                  {(bulkRunning || bulkPaused) && !bulkFinished && (
                    <Button variant="contained" color="error" size="large" onClick={() => { pauseBulkUpload(); setBulkFinished(true); setBulkRunning(false); }}>
                      Stop
                    </Button>
                  )}
                  
                  {etaSeconds !== null && (
                    <Typography variant="body2" sx={{ ml: 2, color: 'text.secondary' }}>
                      ETA: {Math.floor(etaSeconds / 60)}m {etaSeconds % 60}s
                    </Typography>
                  )}
                </Box>

              {/* Progress and Detailed Tracking Table */}
              {(bulkRunning || bulkFinished || bulkFilesData.length > 0) && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Processed {bulkProgress} of {bulkTotal} files
                  </Typography>
                  <LinearProgress variant="determinate" value={bulkTotal > 0 ? (bulkProgress / bulkTotal) * 100 : 0} sx={{ height: 10, borderRadius: 5, mb: 3, backgroundColor: 'rgba(0, 212, 255, 0.1)', '& .MuiLinearProgress-bar': { background: 'linear-gradient(90deg, #00D4FF, #00E676)' } }} />
                  
                  <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.1)' }}>
                    <Table size="small">
                      <TableHead sx={{ background: 'rgba(255,255,255,0.05)' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 600 }}>File Name</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Protected</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Details</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {bulkFilesData.map((row) => (
                          <TableRow key={row.id} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                            <TableCell component="th" scope="row">
                              {row.name}
                            </TableCell>
                            <TableCell sx={{ color: row.protected === 'Decrypted' ? 'success.main' : 'inherit', fontWeight: row.protected === 'Decrypted' ? 600 : 400 }}>
                              {row.protected || 'No'}
                            </TableCell>
                            <TableCell>{renderStatusChip(row.status)}</TableCell>
                            <TableCell sx={{ color: row.status === 'Failed' ? 'error.main' : 'text.secondary' }}>
                              {row.details}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                  
                  {renderFinalReport()}

                </Box>
              )}

            </Box>
          </CardContent>
        </Card>
      )}

      {/* Password Dialog for Single Upload */}
      <Dialog open={passwordRequired} onClose={handlePasswordCancel} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><LockIcon color="primary" /> Password Required</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>This file is encrypted. Please enter the password to unlock and upload it.</DialogContentText>
          <TextField autoFocus margin="dense" label="File Password" type="password" fullWidth variant="outlined" value={passwordInput} onChange={(e) => setPasswordInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handlePasswordSubmit()} error={error === 'Incorrect password. Please try again.'} helperText={error === 'Incorrect password. Please try again.' ? error : ''} />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handlePasswordCancel} color="inherit">Cancel, Download</Button>
          <Button onClick={handlePasswordSubmit} variant="contained" disabled={!passwordInput || uploading}>{uploading ? 'Unlocking...' : 'Unlock & Upload'}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default UploadReportPage;

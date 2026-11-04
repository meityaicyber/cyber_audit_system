import React, { createContext, useState, useContext, useRef, useEffect, useCallback } from 'react';
import { useSnackbar } from 'notistack';
import api from '../api/axios';

const BulkUploadContext = createContext();

export const useBulkUpload = () => useContext(BulkUploadContext);

export const BulkUploadProvider = ({ children }) => {
  const { enqueueSnackbar } = useSnackbar();

  const [bulkFilesData, setBulkFilesData] = useState([]);
  const [bulkProgress, setBulkProgress] = useState(0);
  const [bulkTotal, setBulkTotal] = useState(0);
  const [bulkRunning, setBulkRunning] = useState(false);
  const [bulkPaused, setBulkPaused] = useState(false);
  const [bulkFinished, setBulkFinished] = useState(false);
  const [bulkStartTime, setBulkStartTime] = useState(null);
  const [bulkEndTime, setBulkEndTime] = useState(null);
  const [isWidgetOpen, setIsWidgetOpen] = useState(false);
  const [isWidgetMinimized, setIsWidgetMinimized] = useState(false);
  const [etaSeconds, setEtaSeconds] = useState(null);

  // Use refs for high-frequency updates without causing massive React re-renders
  const bulkFilesDataRef = useRef([]);
  const progressRef = useRef(0);
  const totalRef = useRef(0);
  const isPausedRef = useRef(false);
  const currentIndexRef = useRef(0);
  const updateIntervalRef = useRef(null);
  
  // Store settings for resume
  const passwordMapRef = useRef({});
  const selectedAgencyRef = useRef('');
  const concurrencyRef = useRef(1);
  const extractedPasswordsRef = useRef([]);

  // Sync refs to React state periodically (500ms)
  useEffect(() => {
    if (bulkRunning && !bulkFinished) {
      updateIntervalRef.current = setInterval(() => {
        setBulkFilesData([...bulkFilesDataRef.current]);
        setBulkProgress(progressRef.current);
        
        // Calculate ETA
        const elapsed = (Date.now() - bulkStartTime) / 1000;
        const progress = progressRef.current;
        if (progress > 0 && progress < totalRef.current) {
          const avgTimePerFile = elapsed / progress;
          const remaining = totalRef.current - progress;
          setEtaSeconds(Math.round(avgTimePerFile * remaining));
        }
      }, 500);
    }
    return () => {
      if (updateIntervalRef.current) clearInterval(updateIntervalRef.current);
    };
  }, [bulkRunning, bulkFinished, bulkStartTime]);

  const updateFileStatus = (id, status, details, clearFile = false, protectedStatus = undefined) => {
    const itemIndex = bulkFilesDataRef.current.findIndex(item => item.id === id);
    if (itemIndex > -1) {
      const item = bulkFilesDataRef.current[itemIndex];
      const updates = { status, details };
      if (protectedStatus !== undefined) updates.protected = protectedStatus;
      bulkFilesDataRef.current[itemIndex] = { ...item, ...updates };
      if (clearFile) {
        bulkFilesDataRef.current[itemIndex].file = null; // Free memory!
      }
    }
  };

  const decodeJWT = (token) => {
    try {
      return JSON.parse(atob(token.split('.')[1]));
    } catch (e) {
      return null;
    }
  };

  const checkAndRefreshToken = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    const decoded = decodeJWT(token);
    if (!decoded || !decoded.exp) return;
    
    // If token expires in less than 3 minutes, refresh it
    const expiresAt = decoded.exp * 1000;
    if (expiresAt - Date.now() < 3 * 60 * 1000) {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const res = await api.post('/api/auth/refresh', { refresh_token: refreshToken });
          localStorage.setItem('access_token', res.data.access_token);
          localStorage.setItem('refresh_token', res.data.refresh_token);
        } catch(e) {
          console.error('Proactive token refresh failed', e);
        }
      }
    }
  };

  const processFile = async (fileData, passwordMap, selectedAgency, extractedPasswords = []) => {
    if (isPausedRef.current) return false; // Stopped

    const file = fileData.file;
    if (!file) return true; // Already processed/cleaned

    const cleanName = fileData.name;
    const baseName = cleanName.replace(/\.[^/.]+$/, "");
    const matchedPassword = passwordMap[baseName.toLowerCase()] || passwordMap[cleanName.toLowerCase()] || '';

    let reportId = null;
    let attempt = 0;
    const maxAttempts = 2; // 1 retry

    while (attempt < maxAttempts && !isPausedRef.current) {
      attempt++;
      try {
        const fileStartTime = Date.now();
        await checkAndRefreshToken();

        updateFileStatus(fileData.id, 'Uploading', attempt > 1 ? `Uploading (Retry ${attempt})...` : 'Uploading to storage...');

        const formData = new FormData();
        formData.append('file', file, cleanName);
        if (selectedAgency) formData.append('agency_id', selectedAgency);
        if (matchedPassword) formData.append('file_password', matchedPassword);
        if (extractedPasswords && extractedPasswords.length > 0) formData.append('bulk_passwords', JSON.stringify(extractedPasswords));

        // Upload
        const uploadRes = await api.post('/api/reports/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 0 // Infinite
        });
        reportId = uploadRes.data.report_id;

        // Pipeline
        updateFileStatus(fileData.id, 'Pipeline', attempt > 1 ? `Running Pipeline (Retry ${attempt})...` : 'Running AI Pipeline...');
        
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${api.defaults.baseURL || ''}/api/reports/${reportId}/run-pipeline`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Pipeline error: ${response.status} - ${errText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let chunkCount = 0;
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            chunkCount++;
            // Temporary debug: update UI to show we got a chunk
            updateFileStatus(fileData.id, 'Pipeline', `Receiving data... (chunk ${chunkCount})`);
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep the last incomplete chunk in the buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.substring(6));
                        if (event.type === 'log') {
                            updateFileStatus(fileData.id, 'Pipeline', event.message);
                        } else if (event.type === 'error') {
                            throw new Error(event.message);
                        }
                    } catch (e) {
                        // ignore parse errors
                    }
                }
            }
        }
        
        const timeTaken = ((Date.now() - fileStartTime) / 1000).toFixed(1);
        
        if (uploadRes.data.decrypted || fileData.protected === 'Yes') {
          updateFileStatus(fileData.id, 'Success', `File saved and pipeline completed in ${timeTaken}s.`, true, 'Decrypted');
        } else {
          updateFileStatus(fileData.id, 'Success', `File saved and pipeline completed in ${timeTaken}s.`, true);
        }
        return true; // Success!

      } catch (err) {
        let msg = 'Operation failed';
        const status = err.response?.status;
        
        if (err.response) {
          if (err.response.data && typeof err.response.data.detail === 'string') {
            msg = err.response.data.detail;
          } else if (err.response.data && Array.isArray(err.response.data.detail)) {
            msg = err.response.data.detail.map(d => d.msg || JSON.stringify(d)).join(', ');
          } else if (status === 413) {
            msg = "File size limit exceeded";
          } else if (status === 500) {
             if (typeof err.response.data === 'string' && err.response.data.length < 200 && !err.response.data.includes('<html')) {
                msg = err.response.data;
             } else {
                msg = "Internal server error on backend";
             }
          } else {
            msg = `Request failed with status code ${status}`;
          }
        } else {
          msg = err.message || 'Network error';
        }

        // Determine if transient error (can retry)
        const isTransient = !status || status >= 500 || status === 429;
        
        if (reportId) {
          try {
             await api.delete(`/api/reports/${reportId}`);
          } catch(rollbackErr) {}
        }
        
        if (isTransient && attempt < maxAttempts && !isPausedRef.current) {
           updateFileStatus(fileData.id, 'Retrying', `Transient error: ${msg}. Waiting to retry...`);
           await new Promise(r => setTimeout(r, 2000 * attempt)); // exponential backoff
           continue; // Loop again
        } else {
           updateFileStatus(fileData.id, 'Failed', msg, true);
           return false; // Failed completely
        }
      }
    }
    return false;
  };

  const startQueue = async (filesData, passwordMap, selectedAgency, concurrency, extractedPasswords) => {
    const processNext = async () => {
      while (currentIndexRef.current < totalRef.current && !isPausedRef.current) {
        const localIndex = currentIndexRef.current++;
        const fileData = bulkFilesDataRef.current[localIndex];
        
        // Skip if already processed (for resume functionality)
        if (fileData.status === 'Success' || fileData.status === 'Failed') {
          continue;
        }

        await processFile(fileData, passwordMap, selectedAgency, extractedPasswords);
        
        progressRef.current++;
        
        // Save progress occasionally to localstorage in case of crash
        if (progressRef.current % 10 === 0) {
           saveProgressToLocal();
        }
      }
    };

    const workers = [];
    for (let i = 0; i < concurrency; i++) {
      workers.push(processNext());
    }
    
    await Promise.all(workers);
    
    if (!isPausedRef.current) {
       // Force a final state sync
       setBulkFilesData([...bulkFilesDataRef.current]);
       setBulkProgress(progressRef.current);
       setBulkEndTime(Date.now());
       setBulkRunning(false);
       setBulkFinished(true);
       setEtaSeconds(null);
       enqueueSnackbar('Bulk processing completed', {variant: 'success'});
       localStorage.removeItem('bulkUploadBackup'); // Clear backup
    } else {
       setBulkRunning(false);
       setBulkFilesData([...bulkFilesDataRef.current]);
       setBulkProgress(progressRef.current);
       enqueueSnackbar('Bulk processing paused', {variant: 'info'});
       saveProgressToLocal();
    }
  };

  const startBulkUpload = (filesData, passwordMap, selectedAgency, concurrency, extractedPasswords = []) => {
    passwordMapRef.current = passwordMap || {};
    selectedAgencyRef.current = selectedAgency || '';
    concurrencyRef.current = concurrency || 1;
    extractedPasswordsRef.current = extractedPasswords || [];
    bulkFilesDataRef.current = filesData.map(item => ({...item, status: 'Pending', details: '-'}));
    progressRef.current = 0;
    totalRef.current = filesData.length;
    currentIndexRef.current = 0;
    isPausedRef.current = false;
    
    setBulkRunning(true);
    setBulkPaused(false);
    setBulkFinished(false);
    setBulkProgress(0);
    setBulkTotal(filesData.length);
    setBulkStartTime(Date.now());
    setBulkEndTime(null);
    setIsWidgetOpen(true);
    setIsWidgetMinimized(false);
    setEtaSeconds(null);

    startQueue(filesData, passwordMapRef.current, selectedAgencyRef.current, concurrencyRef.current, extractedPasswordsRef.current);
  };
  
  const pauseBulkUpload = () => {
    isPausedRef.current = true;
    setBulkPaused(true);
  };
  
  const resumeBulkUpload = () => {
    isPausedRef.current = false;
    setBulkPaused(false);
    setBulkRunning(true);
    startQueue(bulkFilesDataRef.current, passwordMapRef.current, selectedAgencyRef.current, concurrencyRef.current, extractedPasswordsRef.current);
  };

  const saveProgressToLocal = () => {
     // Save everything EXCEPT the file objects (which can't be serialized and take too much memory)
     const backup = {
       filesData: bulkFilesDataRef.current.map(f => ({ ...f, file: null })),
       progress: progressRef.current,
       total: totalRef.current,
       currentIndex: currentIndexRef.current,
       extractedPasswords: extractedPasswordsRef.current
     };
     localStorage.setItem('bulkUploadBackup', JSON.stringify(backup));
  };
  
  // You would ideally load this on component mount if a user refreshes the page
  const loadProgressFromLocal = () => {
     const backupStr = localStorage.getItem('bulkUploadBackup');
     if (backupStr) {
        // Needs user to re-select files to reconnect `file` objects, but status is saved.
        // This is complex for file inputs, so for now we use it mostly for state recovery if the tab doesn't crash completely.
     }
  };

  const closeWidget = () => {
    setIsWidgetOpen(false);
  };

  const toggleMinimize = () => {
    setIsWidgetMinimized(prev => !prev);
  };

  const resetBulkState = () => {
     bulkFilesDataRef.current = [];
     progressRef.current = 0;
     totalRef.current = 0;
     setBulkFilesData([]);
     setBulkProgress(0);
     setBulkTotal(0);
     setBulkRunning(false);
     setBulkFinished(false);
     setBulkPaused(false);
     setBulkStartTime(null);
     setBulkEndTime(null);
     setIsWidgetOpen(false);
     setEtaSeconds(null);
     localStorage.removeItem('bulkUploadBackup');
  };

  return (
    <BulkUploadContext.Provider value={{
      bulkFilesData, setBulkFilesData, bulkProgress, bulkTotal, bulkRunning, bulkFinished, setBulkFinished,
      bulkStartTime, bulkEndTime, isWidgetOpen, isWidgetMinimized, bulkPaused, etaSeconds,
      startBulkUpload, pauseBulkUpload, resumeBulkUpload, closeWidget, toggleMinimize, resetBulkState
    }}>
      {children}
    </BulkUploadContext.Provider>
  );
};

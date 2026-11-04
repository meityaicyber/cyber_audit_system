const express = require('express');
const { exec } = require('child_process');
const path = require('path');
const util = require('util');
const execPromise = util.promisify(exec);
const app = express();
const port = 8005;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Basic error checking helper
const getErrorLogs = (logs) => {
    return logs.split('\n').filter(line => 
        line.toLowerCase().includes('error') || 
        line.toLowerCase().includes('exception') ||
        line.toLowerCase().includes('fail') ||
        line.toLowerCase().includes('502') ||
        line.toLowerCase().includes('504')
    ).join('\n');
};

const hasRecentErrors = async (containerName) => {
    try {
        const { stdout, stderr } = await execPromise(`docker logs --tail 50 ${containerName}`);
        const logs = stderr + stdout;
        const errorLogs = getErrorLogs(logs);
        return errorLogs.trim().length > 0;
    } catch (e) {
        return false;
    }
};

app.get('/', async (req, res) => {
    try {
        const { stdout } = await execPromise('docker ps -a --format "{{.Names}}|{{.State}}|{{.Status}}"');
        let containers = stdout.trim().split('\n').filter(Boolean).map(line => {
            const [name, state, status] = line.split('|');
            return { name, state, status };
        });

        // Filter out old removed containers just in case, though they shouldn't show in ps -a if removed
        // Now check for errors concurrently
        await Promise.all(containers.map(async (container) => {
            container.hasError = await hasRecentErrors(container.name);
        }));

        res.render('index', { containers });
    } catch (err) {
        res.status(500).send("Error fetching services: " + err.message);
    }
});

app.get('/logs/:containerName', async (req, res) => {
    const containerName = req.params.containerName;
    const filter = req.query.filter === 'errors';
    
    try {
        const { stdout, stderr } = await execPromise(`docker logs --tail 500 ${containerName}`);
        let logs = stderr + stdout; 
        if (filter) {
            logs = getErrorLogs(logs);
        }
        res.render('logs', { containerName, logs, filter });
    } catch (err) {
        res.status(500).send("Error fetching logs: " + err.message);
    }
});

app.listen(port, () => {
    console.log(`Service dashboard running at http://localhost:${port}`);
});

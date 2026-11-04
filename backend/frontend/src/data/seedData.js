export const agencies = Array.from({ length: 10 }, (_, i) => ({
  id: `agency-${i + 1}`,
  name: `Agency ${i + 1} (${['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta', 'Iota', 'Kappa'][i]})`,
}));

const severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'];
const statuses = ['OPEN', 'CLOSED', 'ACCEPTED', 'RISK_ACCEPTED', 'IN_PROGRESS'];
const categories = ['Injection', 'Broken Authentication', 'Sensitive Data Exposure', 'XML External Entities (XXE)', 'Broken Access Control', 'Security Misconfiguration', 'Cross-Site Scripting (XSS)', 'Insecure Deserialization', 'Using Components with Known Vulnerabilities', 'Insufficient Logging & Monitoring'];

const generateVulnerabilities = (count) => {
  return Array.from({ length: count }, (_, i) => ({
    id: `vuln-${Math.random().toString(36).substr(2, 9)}`,
    title: `Vulnerability ${i + 1}`,
    severity: severities[Math.floor(Math.random() * severities.length)],
    status: statuses[Math.floor(Math.random() * statuses.length)],
    cvss: parseFloat((Math.random() * 10).toFixed(1)),
    category: categories[Math.floor(Math.random() * categories.length)],
    date: new Date(Date.now() - Math.floor(Math.random() * 10000000000)).toISOString(),
    cwe: `CWE-${Math.floor(Math.random() * 1000)}`,
    cve: `CVE-202${Math.floor(Math.random() * 4)}-${Math.floor(Math.random() * 9000) + 1000}`,
    asset: `192.168.1.${Math.floor(Math.random() * 255)}`,
    new_or_repeat: Math.random() > 0.5 ? 'NEW' : 'REPEAT',
  }));
};

export const files = Array.from({ length: 50 }, (_, i) => ({
  id: `file-${i + 1}`,
  agencyId: agencies[i % 10].id, // 5 files per agency
  name: `Audit_Report_v${Math.floor(Math.random() * 10)}.${Math.floor(Math.random() * 10)}.pdf`,
  date: new Date(Date.now() - Math.floor(Math.random() * 10000000000)).toISOString(),
  detailed_observations: generateVulnerabilities(Math.floor(Math.random() * 15) + 5), // 5-20 vulns per file
}));

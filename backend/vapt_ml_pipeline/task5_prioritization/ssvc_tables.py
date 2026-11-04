# SSVC Decision Table logic

def get_exploitation(poc: str, has_epss: bool, observation: str) -> str:
    """
    Uses explicit proof_of_concept presence or EPSS as primary signals,
    falling back to keyword scanning detailed observation.
    """
    if has_epss:
        # Assuming EPSS > 0 means there is a known CVE with some exploitation probability (poc/active)
        return "poc"
        
    if poc and str(poc).strip() != "None" and str(poc).strip() != "":
        return "poc"
        
    obs = str(observation).lower()
    if "actively exploited" in obs or "exploit observed in the wild" in obs:
        return "active"
        
    return "none"

def get_technical_impact(severity: str) -> str:
    sev = str(severity).lower()
    if sev in ["critical", "high"]:
        return "total"
    return "partial"

def get_automatable(category: str, cwe_ids: list) -> str:
    cat = str(category).lower()
    cwes = [str(x).upper() for x in cwe_ids] if isinstance(cwe_ids, list) else []
    
    # Prior logic: category string matching
    if "remote" in cat and "unauthenticated" in cat:
        return "yes"
        
    # New logic: explicitly check CWEs known for easy automation
    # E.g., SQLi(89), XSS(79), Command Injection(78), Path Traversal(22), Code Injection(94)
    automatable_cwes = ["CWE-89", "CWE-79", "CWE-78", "CWE-22", "CWE-94"]
    if any(cwe in automatable_cwes for cwe in cwes):
        return "yes"
        
    return "no"

def decide_ssvc(exploitation: str, technical_impact: str, automatable: str, mission_prevalence: str) -> str:
    if exploitation == "active":
        if mission_prevalence == "High":
            return "Act"
        if technical_impact == "total":
            return "Act"
        return "Attend"
        
    if exploitation == "poc":
        if technical_impact == "total" and mission_prevalence == "High":
            return "Attend"
        if automatable == "yes":
            return "Attend"
        return "Track*"
        
    if technical_impact == "total" and mission_prevalence == "High":
        return "Track*"
    
    return "Track"

def compute_ssvc_outcome(finding: dict) -> str:
    exp = get_exploitation(finding.get('proof_of_concept'), finding.get('epss_score') is not None, finding.get('detailed_observation'))
    imp = get_technical_impact(finding.get('severity'))
    auto = get_automatable(finding.get('category'), finding.get('cwe_ids', []))
    
    crit = finding.get('asset_criticality', 'Low') 
    
    return decide_ssvc(exp, imp, auto, crit)

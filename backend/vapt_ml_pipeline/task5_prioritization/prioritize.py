import os
import json
import pandas as pd
from vapt_ml_pipeline.config import OUTPUTS_DIR, PRIORITY_WEIGHTS, SSVC_URGENCY_MAP, ASSET_CRITICALITY_MAP
from vapt_ml_pipeline.task5_prioritization.ssvc_tables import compute_ssvc_outcome
from vapt_ml_pipeline.task5_prioritization.epss_client import get_epss_score

def compute_survivability_weight(reval_status: str, report_type: str) -> float:
    """
    Applies an explicit penalty weight if a finding has survived multiple audit cycles.
    """
    if str(report_type).lower() in ['follow-up', 'revalidation'] and str(reval_status).lower() in ['open', 'not fixed', 'partially fixed']:
        return 1.25 # 25% bump in priority score for lingering vulnerabilities
    return 1.0

def run_prioritization(findings_df: pd.DataFrame, reports_df: pd.DataFrame, severity_results: list):
    out_dir = os.path.join(OUTPUTS_DIR, "task5_prioritization")
    
    sev_df = pd.DataFrame(severity_results)
    
    if not sev_df.empty and 'finding_id' in sev_df.columns:
        df = pd.merge(findings_df, sev_df[['finding_id', 'cvss_score_computed', 'severity_llm']], on='finding_id', how='left')
    else:
        df = findings_df.copy()
        df['cvss_score_computed'] = None
        df['severity_llm'] = df['severity']
        
    # Gating filter: Only open findings enter prioritization (status == Open | Partially Fixed)
    open_df = df[df['status'].astype(str).str.lower().isin(['open', 'partially fixed', 'none', 'null', '']) | df['status'].isna()].copy()
    
    results = []
    
    for idx, row in open_df.iterrows():
        # Get EPSS via explicit CVE join key fallback
        epss_scores = []
        cves = row.get('cve_ids', [])
        if isinstance(cves, list) and len(cves) > 0:
            for cve in cves:
                s = get_epss_score(cve)
                if s is not None:
                    epss_scores.append(s)
        epss = max(epss_scores) if epss_scores else None
        
        # Asset Crit: directly mapped from scope in the new loader
        crit = row.get('asset_criticality', 'Medium')
        
        f_dict = row.to_dict()
        f_dict['epss_score'] = epss
        f_dict['severity'] = row.get('severity_llm') or row.get('severity')
        
        ssvc_outcome = compute_ssvc_outcome(f_dict)
        
        cvss = row.get('cvss_score_computed')
        if cvss is None:
            try: cvss = float(row.get('cvss_score')) if pd.notna(row.get('cvss_score')) else 0.0
            except: cvss = 0.0
                
        norm_cvss = cvss / 10.0
        ssvc_w = SSVC_URGENCY_MAP.get(ssvc_outcome, 0.0)
        crit_w = ASSET_CRITICALITY_MAP.get(crit, 0.5)
        
        w_cvss = PRIORITY_WEIGHTS['w1_cvss']
        w_epss = PRIORITY_WEIGHTS['w2_epss']
        w_crit = PRIORITY_WEIGHTS['w3_asset_criticality']
        w_ssvc = PRIORITY_WEIGHTS['w4_ssvc_urgency']
        
        if epss is None:
            total_w = w_cvss + w_crit + w_ssvc
            base_score = (w_cvss/total_w)*norm_cvss + (w_crit/total_w)*crit_w + (w_ssvc/total_w)*ssvc_w
        else:
            base_score = w_cvss*norm_cvss + w_epss*epss + w_crit*crit_w + w_ssvc*ssvc_w
            
        # Survivability multiplier
        surv_weight = compute_survivability_weight(row.get('revalidation_status'), row.get('report_type'))
        final_score = min(1.0, base_score * surv_weight)
            
        rationale = f"{ssvc_outcome} — "
        if surv_weight > 1.0: rationale += "[Lingering Vulnerability] "
        if epss: rationale += f"active exploitation signal (EPSS {epss:.2f}), "
        rationale += f"{f_dict['severity']} severity, deployed on a {crit}-criticality asset."
        
        results.append({
            "finding_id": row['finding_id'],
            "report_id": row['report_id'],
            "ssvc_outcome": ssvc_outcome,
            "epss_score": epss,
            "cvss_score": cvss,
            "asset_criticality": crit,
            "priority_score": final_score,
            "rationale": rationale
        })
        
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        res_df = res_df.sort_values(by='priority_score', ascending=False).reset_index(drop=True)
        res_df['priority_rank_global'] = res_df.index + 1
        res_df['priority_rank_within_report'] = res_df.groupby('report_id')['priority_score'].rank(ascending=False, method='min')
        final_results = res_df.to_dict(orient='records')
    else:
        final_results = []
        
    with open(os.path.join(out_dir, "priority_list.json"), "w") as f:
        json.dump(final_results, f, indent=2)
        
    return final_results

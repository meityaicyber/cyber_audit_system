import os
import json
import pandas as pd
import numpy as np
from vapt_ml_pipeline.config import OUTPUTS_DIR, ANOMALY_PERCENTILE_THRESHOLD

def run_anomaly_detection(reports_df: pd.DataFrame, findings_df: pd.DataFrame):
    if len(reports_df) < 5:
        print("Not enough reports for meaningful anomaly detection.")
        return []
        
    out_dir = os.path.join(OUTPUTS_DIR, "task4_anomaly")
    
    # Create simple encodings for categorical control variables
    unique_orgs = reports_df['auditing_organization'].unique()
    org_map = {org: i for i, org in enumerate(unique_orgs)}
    unique_types = reports_df['audit_type'].unique()
    type_map = {t: i for i, t in enumerate(unique_types)}
    
    feature_rows = []
    r_ids = []
    
    for _, r in reports_df.iterrows():
        rid = r['report_id']
        f_df = findings_df[findings_df['report_id'] == rid]
        
        total = max(1, r.get('total_vulns', 1))
        crit_prop = r.get('critical_count', 0) / total
        
        # New or repeat ratio
        repeat_count = len(f_df[f_df['new_or_repeat'].str.lower() == 'repeat'])
        repeat_ratio = repeat_count / max(1, len(f_df))
        
        # Mean CVSS
        cvss_scores = pd.to_numeric(f_df['cvss_score'], errors='coerce').dropna()
        mean_cvss = cvss_scores.mean() if not cvss_scores.empty else 0.0
        
        # Open Critical Count normalized by Assets Tested
        open_crit = len(f_df[(f_df['severity'].str.lower() == 'critical') & (f_df['status'].str.lower() == 'open')])
        assets_tested = max(1, r.get('assets_tested_count', 1))
        open_crit_per_asset = open_crit / assets_tested
        
        # Covariates
        tools_used = float(r.get('tools_used_count', 0))
        audit_type_val = float(type_map.get(r.get('audit_type'), 0))
        auditing_org_val = float(org_map.get(r.get('auditing_organization'), 0))
        
        feature_rows.append([
            crit_prop, repeat_ratio, mean_cvss, open_crit_per_asset, 
            tools_used, audit_type_val, auditing_org_val
        ])
        r_ids.append(rid)
        
    X = np.array(feature_rows)
    feature_names = [
        "Critical_Proportion", "Repeat_Ratio", "Mean_CVSS", "Open_Critical_Per_Asset",
        "Tools_Used_Count", "Audit_Type", "Auditing_Organization"
    ]
    
    # Calculate Z-scores for explainability
    means = np.mean(X, axis=0)
    stds = np.std(X, axis=0) + 1e-9
    Z = (X - means) / stds
    
    try:
        from pyod.models.ecod import ECOD
        from pyod.models.iforest import IForest
        from pyod.models.lof import LOF
        
        detectors = {
            "ecod": ECOD(),
            "iforest": IForest(random_state=42),
            "lof": LOF()
        }
        
        scores_dict = {}
        for name, clf in detectors.items():
            clf.fit(X)
            scores = clf.decision_scores_
            ranks = pd.Series(scores).rank(pct=True).values
            scores_dict[name] = ranks
            
        ensemble_score = np.mean([scores_dict['ecod'], scores_dict['iforest'], scores_dict['lof']], axis=0)
        
    except ImportError:
        print("PyOD not available, falling back to IForest only via scikit-learn.")
        from sklearn.ensemble import IsolationForest
        clf = IsolationForest(random_state=42)
        clf.fit(X)
        scores = -clf.score_samples(X) 
        ranks = pd.Series(scores).rank(pct=True).values
        scores_dict = {"iforest_fallback": ranks}
        ensemble_score = ranks
        
    results = []
    for i, rid in enumerate(r_ids):
        is_anom = ensemble_score[i] >= ANOMALY_PERCENTILE_THRESHOLD
        
        z_scores = Z[i]
        top_indices = np.argsort(np.abs(z_scores))[::-1][:2] 
        
        explanations = []
        if is_anom:
            for idx in top_indices:
                feat = feature_names[idx]
                z_val = z_scores[idx]
                direction = "above" if z_val > 0 else "below"
                explanations.append(f"{feat} is {abs(z_val):.1f} std deviations {direction} average.")
                
        res = {
            "report_id": rid,
            "ensemble_score": float(ensemble_score[i]),
            "is_anomaly": bool(is_anom),
            "contributing_features": explanations
        }
        for name, s in scores_dict.items():
            res[f"{name}_score"] = float(s[i])
            
        results.append(res)
        
    with open(os.path.join(out_dir, "report_anomalies.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    return results

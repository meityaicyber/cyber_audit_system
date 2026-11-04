import os
import json
import glob
import pandas as pd
from datetime import datetime
from vapt_ml_pipeline.config import SCHEMA_PATH
from vapt_ml_pipeline.data.schema_validate import validate_report

def load_reports(dir_path: str) -> list[dict]:
    """Load and validate all JSON reports in the given directory."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        return []

    reports = []
    skipped_log = []
    
    for fp in glob.glob(os.path.join(dir_path, "*.json")):
        if fp.endswith("master.schema.json") or fp.endswith("masterjson strcture.json"):
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "metadata" not in data or "vulnerabilities" not in data:
                skipped_log.append(f"{fp}: Missing 'metadata' or 'vulnerabilities' keys.")
                continue
            if validate_report(data, SCHEMA_PATH):
                reports.append(data)
            else:
                skipped_log.append(f"{fp}: Failed schema validation.")
        except Exception as e:
            skipped_log.append(f"{fp}: Error reading file: {e}")
            
    if skipped_log:
        with open(os.path.join(os.path.dirname(dir_path), "..", "outputs", "skipped_reports.log"), "w") as f:
            f.write("\n".join(skipped_log))
            
    return reports

def build_dataframes(reports: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flatten reports into reports_df and findings_df with enhanced feature engineering."""
    reports_data = []
    findings_data = []
    
    def parse_date(date_str):
        if not date_str: return None
        try: return pd.to_datetime(date_str)
        except: return None
        
    for r in reports:
        meta = r.get("metadata", {})
        exec_sum = r.get("executive_summary", {})
        scope = r.get("scope", {})
        testing_period = scope.get("testing_period", {})
        vulns = r.get("vulnerabilities", [])
        
        report_id = meta.get("document_id") or f"report_{hash(json.dumps(r))}"
        
        test_start = parse_date(testing_period.get("start_date"))
        test_end = parse_date(testing_period.get("end_date"))
        testing_duration_days = (test_end - test_start).days if pd.notnull(test_start) and pd.notnull(test_end) else 1
        
        assets = scope.get("assets_tested", [])
        assets_tested_count = max(1, len(assets)) # Prevent div by zero
        
        # Build mapping for finding level criticality joining
        asset_crit_map = {}
        for a in assets:
            if a.get("asset_name"): asset_crit_map[str(a.get("asset_name")).lower()] = a.get("criticality", "Medium")
            if a.get("public_ip"): asset_crit_map[str(a.get("public_ip")).lower()] = a.get("criticality", "Medium")
            if a.get("internal_ip"): asset_crit_map[str(a.get("internal_ip")).lower()] = a.get("criticality", "Medium")
            
        repeat_count = sum(1 for v in vulns if str(v.get("new_or_repeat")).lower() == "repeat")
        repeat_ratio = repeat_count / max(1, len(vulns))
        
        total_vulns = int(exec_sum.get("total_vulnerabilities") or len(vulns))
        crit_count = int(exec_sum.get("critical_count") or 0)
        
        reports_data.append({
            "report_id": report_id,
            "org": meta.get("organization_audited", "Unknown"),
            "audit_type": meta.get("audit_type", "Unknown"),
            "report_type": meta.get("report_type", "Unknown"),
            "release_date": parse_date(meta.get("release_date")),
            "test_start": test_start,
            "test_end": test_end,
            "testing_duration_days": testing_duration_days,
            "auditing_organization": meta.get("auditing_organization", "Unknown"),
            "standards_referenced_count": len(meta.get("standards_referenced", [])),
            "tools_used_count": len(r.get("tools_used", [])),
            "assets_tested_count": assets_tested_count,
            "total_vulns": total_vulns,
            "critical_count": crit_count,
            "high_count": int(exec_sum.get("high_count") or 0),
            "medium_count": int(exec_sum.get("medium_count") or 0),
            "low_count": int(exec_sum.get("low_count") or 0),
            "info_count": int(exec_sum.get("informational_count") or 0),
            "summary_text": exec_sum.get("summary_text", ""),
            "repeat_ratio": repeat_ratio,
            "total_vulns_per_asset": total_vulns / assets_tested_count,
            "critical_count_per_asset": crit_count / assets_tested_count
        })
        
        for v in vulns:
            cvss_raw = v.get("cvss_score")
            try: cvss_float = float(cvss_raw) if cvss_raw is not None else None
            except ValueError: cvss_float = None
                
            affected = v.get("affected_assets", [])
            
            # Map structured criticality from scope.assets_tested
            finding_crit = "Medium"
            if isinstance(affected, list):
                for a in affected:
                    c = asset_crit_map.get(str(a).lower())
                    if c:
                        finding_crit = c
                        if str(c).lower() == "high": break # Highest takes precedence
                        
            findings_data.append({
                "report_id": report_id,
                "finding_id": v.get("id", ""),
                "title": v.get("vulnerability_title", ""),
                "category": v.get("category"),
                "severity": v.get("severity"),
                "cvss_score": cvss_float,
                "cvss_raw": cvss_raw,
                "cve_ids": v.get("cve_ids", []),
                "cwe_ids": v.get("cwe_ids", []),
                "affected_assets": affected,
                "asset_criticality": finding_crit, # Added explicitly from scope
                "status": v.get("status"),
                "new_or_repeat": v.get("new_or_repeat"),
                "description": v.get("description", ""),
                "detailed_observation": v.get("detailed_observation", ""),
                "impact": v.get("impact", ""),
                "recommendation": v.get("recommendation", ""),
                "proof_of_concept": v.get("proof_of_concept"),
                "revalidation_status": v.get("revalidation_status"),
                "report_type": meta.get("report_type", "Unknown") # Copied to finding for prioritization
            })
            
    return pd.DataFrame(reports_data) if reports_data else pd.DataFrame(), pd.DataFrame(findings_data) if findings_data else pd.DataFrame()

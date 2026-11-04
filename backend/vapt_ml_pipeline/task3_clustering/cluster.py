import os
import json
import pandas as pd
import numpy as np
from vapt_ml_pipeline.config import OUTPUTS_DIR
from vapt_ml_pipeline.common.embeddings import get_embedding_model

def run_clustering(reports_df: pd.DataFrame, findings_df: pd.DataFrame):
    out_dir = os.path.join(OUTPUTS_DIR, "task3_clustering")
    
    # 1. Finding-level topic clustering
    finding_topics_info = []
    if len(findings_df) >= 10:
        try:
            from bertopic import BERTopic
            
            # Enrich embedding text with category, CWE, and impact
            def format_finding_text(row):
                cat = row.get('category', '')
                cwe = ','.join(row.get('cwe_ids', [])) if isinstance(row.get('cwe_ids'), list) else str(row.get('cwe_ids', ''))
                title = row.get('title', '')
                desc = row.get('description', '')
                impact = row.get('impact', '')
                return f"[{cat}] CWE:{cwe} | {title}. {desc} Impact: {impact}"
                
            texts = findings_df.apply(format_finding_text, axis=1).tolist()
            min_topic_size = max(3, int(0.02 * len(findings_df)))
            
            emb_model = get_embedding_model()
            topic_model = BERTopic(embedding_model=emb_model, min_topic_size=min_topic_size)
            topics, probs = topic_model.fit_transform(texts)
            
            topic_info_df = topic_model.get_topic_info()
            for _, row in topic_info_df.iterrows():
                t_id = row['Topic']
                name = "Outliers/Noise" if t_id == -1 else row['Name']
                
                member_idx = [i for i, t in enumerate(topics) if t == t_id]
                member_ids = findings_df.iloc[member_idx]['finding_id'].tolist()
                
                finding_topics_info.append({
                    "topic_id": t_id,
                    "name": name,
                    "count": row['Count'],
                    "member_finding_ids": member_ids
                })
        except Exception as e:
            print(f"Finding clustering failed: {e}")
            
    # 2. Report-level clustering (mixed features)
    report_clusters = []
    if len(reports_df) >= 5:
        try:
            import umap
            import hdbscan
            
            features = []
            valid_reports = []
            
            # Create simple encodings for auditing_org to include in structural features
            unique_orgs = reports_df['auditing_organization'].unique()
            org_map = {org: i for i, org in enumerate(unique_orgs)}
            
            for idx, r in reports_df.iterrows():
                total = max(1, r.get('total_vulns', 1))
                crit_prop = r.get('critical_count', 0) / total
                high_prop = r.get('high_count', 0) / total
                med_prop = r.get('medium_count', 0) / total
                
                a_type = str(r.get('audit_type', '')).lower()
                type_val = 1 if 'web' in a_type else (2 if 'api' in a_type else (3 if 'network' in a_type else 0))
                
                # New Structural dimensions
                assets_count = float(r.get('assets_tested_count', 1.0))
                org_val = float(org_map.get(r.get('auditing_organization'), 0))
                
                text = r.get('summary_text', '')
                emb_model = get_embedding_model()
                text_emb = emb_model.encode([text])[0]
                
                # Combine structure (now with 6 dims) + text embedding
                struc = np.array([crit_prop, high_prop, med_prop, type_val, assets_count, org_val])
                vec = np.concatenate([struc, text_emb])
                features.append(vec)
                valid_reports.append(r['report_id'])
                
            features = np.array(features)
            
            n_neighbors = min(15, len(features) - 1)
            reducer = umap.UMAP(n_neighbors=n_neighbors, min_dist=0.1, n_components=2, random_state=42)
            reduced = reducer.fit_transform(features)
            
            clusterer = hdbscan.HDBSCAN(min_cluster_size=max(2, int(0.05 * len(features))))
            cluster_labels = clusterer.fit_predict(reduced)
            
            for r_id, cid in zip(valid_reports, cluster_labels):
                report_clusters.append({
                    "report_id": r_id,
                    "cluster_id": int(cid),
                    "description": "Noise/Outlier" if cid == -1 else f"Cluster {cid}"
                })
        except Exception as e:
            print(f"Report clustering failed: {e}")
            
    with open(os.path.join(out_dir, "finding_topics.json"), "w") as f:
        json.dump(finding_topics_info, f, indent=2)
        
    with open(os.path.join(out_dir, "report_clusters.json"), "w") as f:
        json.dump(report_clusters, f, indent=2)
        
    return finding_topics_info, report_clusters

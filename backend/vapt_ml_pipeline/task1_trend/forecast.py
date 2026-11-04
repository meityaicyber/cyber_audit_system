import os
import json
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional
import plotly.graph_objects as go
from vapt_ml_pipeline.config import AUDIT_HEALTH_WEIGHTS, OUTPUTS_DIR, FORECAST_HORIZON, MIN_HISTORY_FOR_FORECAST

@dataclass
class ForecastResult:
    point: list[float]
    low_80: list[float]
    high_80: list[float]
    low_95: list[float]
    high_95: list[float]
    model_used: str
    insufficient_history: bool

def _fallback_linear(series: pd.Series, horizon: int) -> ForecastResult:
    if len(series) < 2:
        return ForecastResult([], [], [], [], [], "none", True)
    
    x = np.arange(len(series))
    y = series.values
    slope, intercept = np.polyfit(x, y, 1)
    
    point_fcst = []
    for i in range(horizon):
        point_fcst.append(slope * (len(series) + i) + intercept)
        
    std = np.std(y) if len(y) > 1 else 1.0
    return ForecastResult(
        point=point_fcst,
        low_80=[p - 1.28*std for p in point_fcst],
        high_80=[p + 1.28*std for p in point_fcst],
        low_95=[p - 1.96*std for p in point_fcst],
        high_95=[p + 1.96*std for p in point_fcst],
        model_used="linear_trend",
        insufficient_history=False
    )

def _fallback_arima(series: pd.Series, horizon: int) -> ForecastResult:
    try:
        from statsmodels.tsa.arima.model import ARIMA
        model = ARIMA(series.values, order=(1,1,0))
        res = model.fit()
        fcst = res.get_forecast(steps=horizon)
        point = fcst.predicted_mean.tolist()
        ci_80 = fcst.conf_int(alpha=0.2)
        ci_95 = fcst.conf_int(alpha=0.05)
        
        return ForecastResult(
            point=point,
            low_80=ci_80[:, 0].tolist(),
            high_80=ci_80[:, 1].tolist(),
            low_95=ci_95[:, 0].tolist(),
            high_95=ci_95[:, 1].tolist(),
            model_used="arima_1_1_0",
            insufficient_history=False
        )
    except Exception as e:
        print(f"ARIMA fallback failed: {e}")
        return _fallback_linear(series, horizon)

def forecast_metric(series: pd.Series, horizon: int = FORECAST_HORIZON) -> ForecastResult:
    if len(series) < MIN_HISTORY_FOR_FORECAST:
        return ForecastResult([], [], [], [], [], "none", True)
        
    try:
        import torch
        from chronos import ChronosPipeline
        
        pipeline = ChronosPipeline.from_pretrained(
            "amazon/chronos-bolt-small", 
            device_map="cpu", 
            torch_dtype=torch.float32
        )
        
        tensor_series = torch.tensor(series.values, dtype=torch.float32)
        samples = pipeline.predict(tensor_series.unsqueeze(0), prediction_length=horizon, num_samples=20)
        samples_np = samples[0].numpy()
        
        point = np.median(samples_np, axis=0).tolist()
        low_80 = np.percentile(samples_np, 10, axis=0).tolist()
        high_80 = np.percentile(samples_np, 90, axis=0).tolist()
        low_95 = np.percentile(samples_np, 2.5, axis=0).tolist()
        high_95 = np.percentile(samples_np, 97.5, axis=0).tolist()
        
        return ForecastResult(
            point=point, low_80=low_80, high_80=high_80, 
            low_95=low_95, high_95=high_95, 
            model_used="chronos-2", insufficient_history=False
        )
    except Exception as e:
        print(f"Chronos failed/unavailable, falling back: {e}")
        if len(series) >= 6:
            return _fallback_arima(series, horizon)
        else:
            return _fallback_linear(series, horizon)

def plot_forecast(series: pd.Series, fcst: ForecastResult, title: str, save_path: str):
    if fcst.insufficient_history: return
    
    fig = go.Figure()
    x_hist = list(range(len(series)))
    fig.add_trace(go.Scatter(x=x_hist, y=series.values, mode='lines+markers', name='Historical'))
    
    x_fcst = list(range(len(series)-1, len(series) + FORECAST_HORIZON))
    y_point = [series.values[-1]] + fcst.point
    y_low95 = [series.values[-1]] + fcst.low_95
    y_high95 = [series.values[-1]] + fcst.high_95
    
    fig.add_trace(go.Scatter(x=x_fcst, y=y_point, mode='lines+markers', name='Forecast Point', line=dict(dash='dash')))
    fig.add_trace(go.Scatter(x=x_fcst, y=y_high95, mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=x_fcst, y=y_low95, mode='lines', line=dict(width=0), fill='tonexty', name='95% CI', fillcolor='rgba(68, 68, 68, 0.3)'))
    
    fig.update_layout(title=title, xaxis_title="Cycles", yaxis_title="Count / Ratio")
    fig.write_html(save_path)

def run_trend_analysis(reports_df: pd.DataFrame):
    if reports_df.empty:
        return
        
    out_dir = os.path.join(OUTPUTS_DIR, "task1_trend")
    plots_dir = os.path.join(out_dir, "plots")
    
    def compute_health(row):
        penalty = (row['critical_count']*AUDIT_HEALTH_WEIGHTS['critical'] + 
                   row['high_count']*AUDIT_HEALTH_WEIGHTS['high'] + 
                   row['medium_count']*AUDIT_HEALTH_WEIGHTS['medium'] + 
                   row['low_count']*AUDIT_HEALTH_WEIGHTS['low'])
        score = 100 - penalty
        return max(0, min(100, score))
        
    reports_df['audit_health_score'] = reports_df.apply(compute_health, axis=1)
    reports_df = reports_df.sort_values(by='release_date', na_position='first')
    
    summary = {}
    
    # Enhanced metric set as requested
    metrics_to_forecast = [
        'total_vulns', 'critical_count', 'high_count', 'audit_health_score',
        'repeat_ratio', 'total_vulns_per_asset', 'critical_count_per_asset'
    ]
    
    def process_series(group_df, prefix):
        for metric in metrics_to_forecast:
            if metric not in group_df.columns:
                continue
            s = group_df[metric].dropna().reset_index(drop=True)
            res = forecast_metric(s)
            
            flag = "Insufficient history."
            if not res.insufficient_history and len(res.point) > 0:
                slope = (res.point[-1] - s.iloc[-1]) / len(res.point)
                direction = "trending up" if slope > 0 else "trending down"
                flag = f"{metric.replace('_', ' ').capitalize()} {direction}: {slope:+.2f}/cycle"
            
            res_dict = asdict(res)
            res_dict['flag'] = flag
            
            with open(os.path.join(out_dir, f"{prefix}_{metric}.json"), "w") as f:
                json.dump(res_dict, f, indent=2)
                
            summary[f"{prefix}_{metric}"] = flag
            plot_forecast(s, res, f"{prefix} - {metric}", os.path.join(plots_dir, f"{prefix}_{metric}.html"))

    # Global Trend
    process_series(reports_df, "global")
    
    # Per Organization
    for org, group in reports_df.groupby('org'):
        if len(group) >= MIN_HISTORY_FOR_FORECAST:
            org_clean = "".join([c if c.isalnum() else "_" for c in org])
            process_series(group, f"org_{org_clean}")
            
    # Per Audit Type (Covariate Segmentation)
    for a_type, group in reports_df.groupby('audit_type'):
        if len(group) >= MIN_HISTORY_FOR_FORECAST:
            type_clean = "".join([c if c.isalnum() else "_" for c in a_type])
            process_series(group, f"type_{type_clean}")
            
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    
    return summary

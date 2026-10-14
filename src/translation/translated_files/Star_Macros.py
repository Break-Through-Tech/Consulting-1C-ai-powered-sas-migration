import numpy as np
import pandas as pd

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

def keep_hos(indsn, varlist, nmeasure):
    df = indsn.copy()
    m_cols = [v.strip() for v in varlist.split()]
    c_cols = [f"C{i}" for i in range(1, nmeasure + 1)]
    
    for i, m in enumerate(m_cols):
        c = c_cols[i]
        df[c] = df[m].apply(lambda val: 1 if pd.notna(val) else 0)
        
    df['Total_m_cnt'] = df[c_cols].sum(axis=1)
    df = df[df['Total_m_cnt'] >= 1].copy()
    df = df.drop(columns=c_cols + ['k'] if 'k' in df.columns else c_cols)
    return df

def grp_score(indsn, gp, varlist, nmeasure, out_avg):
    df = indsn.copy()
    m_cols = [v.strip() for v in varlist.split()]
    c_cols = [f"C{i}" for i in range(1, nmeasure + 1)]
    
    for i, m in enumerate(m_cols):
        c = c_cols[i]
        df[c] = df[m].apply(lambda val: 1 if pd.notna(val) else 0)
        
    df['total_cnt'] = df[c_cols].sum(axis=1)
    
    def calc_row(row):
        if row['total_cnt'] > 0:
            wt = 1.0 / row['total_cnt']
            s = sum(row[m] for m in m_cols if pd.notna(row[m]))
            return wt, s * wt
        return np.nan, np.nan

    res = df.apply(calc_row, axis=1)
    df['measure_wt'] = [r[0] for r in res]
    df['avg'] = [r[1] for r in res]
    
    keep_cols = ['provider_id'] + m_cols + c_cols + ['total_cnt', 'measure_wt', 'avg']
    dat0 = df[keep_cols].copy()
    
    valid_avg = dat0['avg'].dropna()
    mean_val = valid_avg.mean()
    std_val = valid_avg.std(ddof=1) if len(valid_avg) > 1 else 0.0
    
    dat1 = dat0.copy()
    if std_val != 0:
        dat1['avg'] = (dat1['avg'] - mean_val) / std_val
    else:
        dat1['avg'] = 0.0
        
    new_summary = pd.DataFrame({'mean': [mean_val], 'std': [std_val]})
    
    dat2 = dat0.assign(key=1).merge(new_summary.assign(key=1), on='key').drop(columns='key')
    
    merged = dat2.rename(columns={'avg': 'score_before_std'}).merge(
        dat1[['provider_id', 'avg']].rename(columns={'avg': 'grp_score'}),
        on='provider_id',
        how='inner'
    )
    
    globals()[out_avg] = merged
    return merged

def report(indsn, outdsn, nmeasure_OM, nmeasure_OS, nmeasure_OR, nmeasure_PtExp, nmeasure_Process, measure_OM, measure_OS, measure_OR, measure_PtExp, measure_Process):
    df = indsn.copy()
    
    om_cols = [v.strip() for v in measure_OM.split()]
    os_cols = [v.strip() for v in measure_OS.split()]
    or_cols = [v.strip() for v in measure_OR.split()]
    oh_cols = [v.strip() for v in measure_PtExp.split()]
    op_cols = [v.strip() for v in measure_Process.split()]
    
    for i, m in enumerate(om_cols, 1):
        df[f'M{i}'] = df[m].apply(lambda x: 1 if pd.notna(x) else 0)
    df['Outcomes_Mortality_cnt'] = df[[f'M{i}' for i in range(1, nmeasure_OM + 1)]].sum(axis=1)
    
    for i, m in enumerate(os_cols, 1):
        df[f'S{i}'] = df[m].apply(lambda x: 1 if pd.notna(x) else 0)
    df['Outcomes_safety_cnt'] = df[[f'S{i}' for i in range(1, nmeasure_OS + 1)]].sum(axis=1)
    
    for i, m in enumerate(or_cols, 1):
        df[f'R{i}'] = df[m].apply(lambda x: 1 if pd.notna(x) else 0)
    df['Outcomes_Readmission_cnt'] = df[[f'R{i}' for i in range(1, nmeasure_OR + 1)]].sum(axis=1)
    
    for i, m in enumerate(oh_cols, 1):
        df[f'H{i}'] = df[m].apply(lambda x: 1 if pd.notna(x) else 0)
    df['Patient_Experience_cnt'] = df[[f'H{i}' for i in range(1, nmeasure_PtExp + 1)]].sum(axis=1)
    
    for i, m in enumerate(op_cols, 1):
        df[f'PC{i}'] = df[m].apply(lambda x: 1 if pd.notna(x) else 0)
    df['Process_cnt'] = df[[f'PC{i}' for i in range(1, nmeasure_Process + 1)]].sum(axis=1)
    
    d_cnts = [
        'Patient_Experience_cnt', 'Outcomes_Mortality_cnt', 
        'Outcomes_Readmission_cnt', 'Outcomes_safety_cnt', 'Process_cnt'
    ]
    
    for idx, col in enumerate(d_cnts, 1):
        df[f'D{idx}'] = df[col].apply(lambda x: 1 if x >= 3 else 0)
        
    df['Total_measure_group_cnt'] = df[[f'D{i}' for i in range(1, 6)]].sum(axis=1)
    df['MortSafe_Group_cnt'] = (df['Outcomes_Mortality_cnt'] >= 3).astype(int) + (df['Outcomes_safety_cnt'] >= 3).astype(int)
    df['report_indicator'] = ((df['MortSafe_Group_cnt'] >= 1) & (df['Total_measure_group_cnt'] >= 3)).astype(int)
    
    out_cols = [
        'provider_id', 'report_indicator', 'Patient_Experience_cnt', 
        'Outcomes_Readmission_cnt', 'Outcomes_Mortality_cnt', 
        'Outcomes_safety_cnt', 'Process_cnt', 'Total_measure_group_cnt', 
        'MortSafe_Group_cnt'
    ]
    
    res = df[out_cols].copy()
    globals()[outdsn] = res
    return res

def kmeans(in_df, out, grp):
    summary_score2 = in_df.copy()
    
    pcts = np.percentile(summary_score2['summary_score'].dropna(), [20, 40, 60, 80])
    p20, p40, p60, p80 = pts[0], pts[1], pts[2], pts[3]
    
    def assign_quintile(val):
        if pd.isna(val):
            return np.nan
        elif val <= p20:
            return 1
        elif val <= p40:
            return 2
        elif val <= p60:
            return 3
        elif val <= p80:
            return 4
        else:
            return 5
            
    s2 = summary_score2.copy()
    s2['grp'] = s2['summary_score'].apply(assign_quintile)
    
    s3 = s2.groupby('grp')['summary_score'].median().reset_index()
    s33 = s3.rename(columns={'summary_score': 'summary_score_median'})
    s33['summary_score'] = s33['summary_score_median']
    
    seeds = s33['summary_score'].dropna().values.reshape(-1, 1)
    if len(seeds) < 5:
        seeds = np.linspace(summary_score2['summary_score'].min(), summary_score2['summary_score'].max(), 5).reshape(-1, 1)
        
    X = summary_score2[['summary_score']].fillna(summary_score2['summary_score'].mean()).values
    
    kmeans1 = KMeans(n_clusters=min(5, len(seeds)), init=seeds[:min(5, len(seeds))], n_init=1, max_iter=1000, random_state=42)
    clusters_labels = kmeans1.fit_predict(X)
    
    clusters_df = summary_score2.copy()
    clusters_df['cluster'] = clusters_labels + 1
    cluster_centers1 = pd.DataFrame({'cluster': range(1, len(kmeans1.cluster_centers_) + 1), 'summary_score': kmeans1.cluster_centers_.flatten()})
    
    kmeans2 = KMeans(n_clusters=min(5, len(cluster_centers1)), init=cluster_centers1['summary_score'].values.reshape(-1, 1), n_init=1, max_iter=1000, random_state=42)
    clusters_labels2 = kmeans2.fit_predict(X)
    
    clusters = summary_score2.copy()
    clusters['cluster'] = clusters_labels2 + 1
    cluster_mean = pd.DataFrame({'cluster': range(1, len(kmeans2.cluster_centers_) + 1), 'summary_score': kmeans2.cluster_centers_.flatten()})
    
    cluster_sort = cluster_mean.sort_values(by='summary_score').copy()
    cluster_sort = cluster_sort.rename(columns={'summary_score': 'mean_summary_score_star'})
    cluster_sort['star'] = range(1, len(cluster_sort) + 1)
    cluster_sort['cluster_2'] = cluster_sort['cluster'].astype(str).astype(float).astype(int)
    
    cluster_sort = cluster_sort.rename(columns={'cluster_2': 'cluster'})
    clusters['cluster'] = clusters['cluster'].abs()
    
    results = clusters.merge(cluster_sort[['cluster', 'star']], on='cluster', how='left')
    results = results.sort_values(by='provider_id')
    
    final_out = results[['provider_id', 'star', grp]].copy() if grp in results.columns else results[['provider_id', 'star']].copy()
    globals()[out] = final_out
    return final_out

def nation_avg0(indata, out, var):
    temp = indata[indata['report_indicator'] == 1].copy()
    mean_val = temp['summary_score'].mean()
    out_df = pd.DataFrame({var: [mean_val]})
    globals()[out] = out_df
    return out_df

def nation_avg_peer(indata, out, var, gr):
    temp = indata[indata['report_indicator'] == 1].copy()
    out1 = temp.groupby(gr)['summary_score'].mean().reset_index().rename(columns={'summary_score': var})
    out2 = out1.pivot(columns=gr, values=var).reset_index(drop=True)
    out2.columns = [f"{var}_peer_{c}" for c in out2.columns]
    globals()[out] = out2
    return out2

def nation_avg(indata, out, var):
    temp = indata[indata['total_cnt'] >= 3].copy()
    mean_val = temp['grp_score'].mean()
    out_df = pd.DataFrame({var: [mean_val]})
    globals()[out] = out_df
    return out_df

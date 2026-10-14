import numpy as np
import pandas as pd

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

def keep_hos(df: pd.DataFrame, varlist: list, nmeasure: int) -> pd.DataFrame:
    df_out = df.copy()
    c_cols = [f'c{i}' for i in range(1, nmeasure + 1)]
    
    for i, var in enumerate(varlist):
        c_col = c_cols[i]
        df_out[c_col] = df_out[var].apply(lambda x: 0 if pd.isna(x) else 1)
        
    df_out['Total_m_cnt'] = df_out[c_cols].sum(axis=1)
    df_out = df_out[df_out['Total_m_cnt'] >= 1].drop(columns=c_cols)
    return df_out

def grp_score(df: pd.DataFrame, gp: str, varlist: list, nmeasure: int, out_avg: str) -> dict:
    df_dat0 = df[['provider_id'] + varlist].copy()
    c_cols = [f'c{i}' for i in range(1, nmeasure + 1)]
    
    for i, var in enumerate(varlist):
        c_col = c_cols[i]
        df_dat0[c_col] = df_dat0[var].apply(lambda x: 0 if pd.isna(x) else 1)
        
    df_dat0['total_cnt'] = df_dat0[c_cols].sum(axis=1)
    
    def calc_wt(row):
        return 1.0 / row['total_cnt'] if row['total_cnt'] > 0 else np.nan
        
    def calc_avg(row):
        if row['total_cnt'] > 0:
            vals = [row[v] for v in varlist]
            return np.nansum(vals) * row['measure_wt']
        return np.nan

    df_dat0['measure_wt'] = df_dat0.apply(calc_wt, axis=1)
    df_dat0['avg'] = df_dat0.apply(calc_avg, axis=1)
    
    mean_val = df_dat0['avg'].mean()
    std_val = df_dat0['avg'].std(ddof=1)
    
    df_dat1 = df_dat0.copy()
    if std_val != 0 and not pd.isna(std_val):
        df_dat1['avg'] = (df_dat1['avg'] - mean_val) / std_val
    else:
        df_dat1['avg'] = 0.0
        
    df_dat2 = df_dat0.copy()
    df_dat2['mean'] = mean_val
    df_dat2['std'] = std_val
    
    merged = pd.merge(
        df_dat2.rename(columns={'avg': 'score_before_std'}),
        df_dat1[['provider_id', 'avg']].rename(columns={'avg': 'grp_score'}),
        on='provider_id'
    )
    
    return {out_avg: merged}

def report(df: pd.DataFrame, outdsn: str, measure_OM: list, measure_OS: list, measure_OR: list, measure_PtExp: list, measure_Process: list) -> dict:
    df_out = df[['provider_id']].copy()
    
    def process_group(sub_df, measures, prefix):
        m_cols = []
        for i, m in enumerate(measures, 1):
            col_name = f'{prefix}{i}'
            sub_df[col_name] = sub_df[m].apply(lambda x: 0 if pd.isna(x) else 1)
            m_cols.append(col_name)
        return sub_df[m_cols].sum(axis=1)

    df_out['Outcomes_Mortality_cnt'] = process_group(df, measure_OM, 'M')
    df_out['Outcomes_safety_cnt'] = process_group(df, measure_OS, 'S')
    df_out['Outcomes_Readmission_cnt'] = process_group(df, measure_OR, 'R')
    df_out['Patient_Experience_cnt'] = process_group(df, measure_PtExp, 'H')
    df_out['Process_cnt'] = process_group(df, measure_Process, 'PC')
    
    d_cnts = [
        df_out['Patient_Experience_cnt'],
        df_out['Outcomes_Mortality_cnt'],
        df_out['Outcomes_Readmission_cnt'],
        df_out['Outcomes_safety_cnt'],
        df_out['Process_cnt']
    ]
    
    d_cols = []
    for i, cnt in enumerate(d_cnts, 1):
        d_col = f'D{i}'
        df_out[d_col] = cnt.apply(lambda x: 1 if x >= 3 else 0)
        d_cols.append(d_col)
        
    df_out['Total_measure_group_cnt'] = df_out[d_cols].sum(axis=1)
    df_out['MortSafe_Group_cnt'] = (df_out['Outcomes_Mortality_cnt'] >= 3).astype(int) + (df_out['Outcomes_safety_cnt'] >= 3).astype(int)
    df_out['report_indicator'] = ((df_out['MortSafe_Group_cnt'] >= 1) & (df_out['Total_measure_group_cnt'] >= 3)).astype(int)
    
    keep_cols = [
        'provider_id', 'report_indicator', 'Patient_Experience_cnt', 'Outcomes_Readmission_cnt',
        'Outcomes_Mortality_cnt', 'Outcomes_safety_cnt', 'Process_cnt', 'Total_measure_group_cnt', 'MortSafe_Group_cnt'
    ]
    
    return {outdsn: df_out[keep_cols]}

def kmeans_clust(df: pd.DataFrame, out: str, grp: str) -> dict:
    summary_score2 = df.copy()
    
    quantiles = np.percentile(summary_score2['summary_score'].dropna(), [20, 40, 60, 80])
    p20, p40, p60, p80 = quantiles[0], quantiles[1], quantiles[2], quantiles[3]
    
    def assign_grp(val):
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

    summary_score2['grp'] = summary_score2['summary_score'].apply(assign_grp)
    s3 = summary_score2.groupby('grp')['summary_score'].median().reset_index()
    s3['summary_score'] = s3['summary_score']
    
    initial_seeds = s3['summary_score'].values.reshape(-1, 1)
    
    kmeans1 = KMeans(n_clusters=len(initial_seeds), init=initial_seeds, n_init=1, max_iter=1000, random_state=42)
    summary_score2['cluster'] = kmeans1.fit_predict(summary_score2[['summary_score']])
    
    cluster_mean = summary_score2.groupby('cluster')['summary_score'].mean().reset_index()
    cluster_mean = cluster_mean.sort_values(by='summary_score').reset_index(drop=True)
    cluster_mean['star'] = cluster_mean.index + 1
    cluster_mean = cluster_mean.rename(columns={'summary_score': 'mean_summary_score_star'})
    
    second_seeds = cluster_mean['mean_summary_score_star'].values.reshape(-1, 1)
    kmeans2 = KMeans(n_clusters=len(second_seeds), init=second_seeds, n_init=1, max_iter=1000, random_state=42)
    summary_score2['cluster'] = kmeans2.fit_predict(summary_score2[['summary_score']])
    
    summary_score2['cluster'] = summary_score2['cluster'].abs()
    
    results = pd.merge(summary_score2, cluster_mean, on='cluster', how='left')
    results['Star'] = results['star']
    
    final_cols = ['provider_id', 'Star']
    if grp and grp in results.columns:
        final_cols.append(grp)
        
    return {out: results[final_cols]}

def nation_avg0(indata: pd.DataFrame, out: str, var: str) -> dict:
    temp = indata[indata['report_indicator'] == 1]
    mean_val = temp['summary_score'].mean()
    res = pd.DataFrame({var: [mean_val]})
    return {out: res}

def nation_avg_peer(indata: pd.DataFrame, out: str, var: str, gr: str) -> dict:
    temp = indata[indata['report_indicator'] == 1]
    out1 = temp.groupby(gr)['summary_score'].mean().reset_index()
    out1 = out1.rename(columns={'summary_score': var})
    
    out2 = out1.pivot(columns=gr, values=var).reset_index(drop=True)
    out2 = out2.add_prefix(f'{var}_peer_')
    
    return {out: out2}

def nation_avg(indata: pd.DataFrame, out: str, var: str) -> dict:
    temp = indata[indata['total_cnt'] >= 3]
    mean_val = temp['grp_score'].mean()
    res = pd.DataFrame({var: [mean_val]})
    return {out: res}

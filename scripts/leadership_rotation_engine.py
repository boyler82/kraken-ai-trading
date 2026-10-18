from __future__ import annotations
import json
from typing import Any
import pandas as pd
from lib.decision_registry import write_record
from lib.feature_store import load_features
from lib.research_module_contract import make_result,write_result
from weekly_consolidation_common import ROOT,atomic_write
OUT=ROOT/"DAILY_REPORTS/LEADERSHIP_ROTATION";MAPPING=ROOT/"DATASETS/METADATA/crypto_sector_mapping.csv"
def map_sectors(features:pd.DataFrame,mapping:pd.DataFrame)->pd.DataFrame:
    m=mapping.drop_duplicates("asset");out=features.merge(m[["asset","primary_category","secondary_category","mapping_source","mapping_version","confidence"]],on="asset",how="left");out["primary_category"]=out["primary_category"].fillna("Other / Unclassified");out["mapping_source"]=out["mapping_source"].fillna("UNMAPPED");out["mapping_version"]=out["mapping_version"].fillna("1.0");return out
def analyze(features:pd.DataFrame,mapping:pd.DataFrame,previous:dict|None=None,as_of:Any=None)->dict:
    data=map_sectors(features,mapping);rs_lookup={r.get("asset"):r.get("relative_strength_score") for r in (previous or {}).get("asset_scores",[])};rows=[]
    for sector,g in data.groupby("primary_category",sort=True):
        eligible=g[g["freshness"].astype(str).eq("FRESH")];base=eligible if len(eligible) else g
        vals=lambda col:pd.to_numeric(base.get(col),errors="coerce")
        row={"sector":sector,"asset_count":len(g),"eligible_asset_count":len(eligible),"equal_weight_return_4h":vals("return_4h").mean(),"equal_weight_return_24h":vals("return_24h").mean(),"equal_weight_return_48h":vals("return_48h").mean(),"equal_weight_return_7d":vals("return_7d").mean(),"median_return_24h":vals("return_24h").median(),"btc_relative_return_24h":vals("btc_relative_return_24h").mean(),"breadth_percent_positive":float((vals("return_24h")>0).mean()*100),"breadth_percent_outperforming_btc":float((vals("btc_relative_return_24h")>0).mean()*100),"volume_expansion":vals("volume_ratio").mean(),"volatility_expansion":vals("volatility_expansion").mean(),"average_momentum_score":vals("momentum_score").mean(),"average_relative_strength_score":pd.Series([rs_lookup.get(x) for x in base.asset]).mean(),"top_contributors":base.sort_values("return_24h",ascending=False).asset.head(3).tolist(),"weak_contributors":base.sort_values("return_24h").asset.head(3).tolist()}
        row["sector_leadership_score"]=round(max(0,min(100,50+float(row["btc_relative_return_24h"] or 0)*4+(row["breadth_percent_outperforming_btc"]-50)*.3+float(row["average_momentum_score"] or 0)*.2)),4);rows.append(row)
    rows=sorted(rows,key=lambda r:(-r["sector_leadership_score"],r["sector"]));prior={(r.get("sector")):r.get("leadership_rank") for r in (previous or {}).get("sectors",[])}
    for i,r in enumerate(rows,1):r["leadership_rank"]=i;r["leadership_rank_change"]=None if r["sector"] not in prior else prior[r["sector"]]-i;r["persistence_duration_days"]=None;r["classification"]="INSUFFICIENT_DATA" if r["eligible_asset_count"]<2 else "CURRENT_LEADER" if i<=3 else "EMERGING_LEADER" if (r["leadership_rank_change"] or 0)>2 else "LOSING_LEADERSHIP" if (r["leadership_rank_change"] or 0)<-2 else "LAGGING" if i>len(rows)*.7 else "STABLE_LEADERSHIP"
    return make_result("leadership_rotation","1.0.0",as_of,freshness="FRESH" if len(data[data.freshness=="FRESH"])>=len(data)/2 else "STALE",summary={"sector_count":len(rows),"mapped_assets":int((data.mapping_source!="UNMAPPED").sum()),"unmapped_assets":int((data.mapping_source=="UNMAPPED").sum())},candidates=rows,unknowns=["Unmapped assets remain Other / Unclassified","Rank persistence unavailable on first run"],source_files=[str(MAPPING),str(ROOT/"DATASETS/FEATURE_STORE/latest_market_features.csv")])
def run(as_of=None):
    prior_path=OUT/"latest_leadership_rotation.json";prior=json.loads(prior_path.read_text()) if prior_path.exists() else {};result=analyze(load_features(),pd.read_csv(MAPPING),prior,as_of);OUT.mkdir(parents=True,exist_ok=True);base=OUT/f"{result['report_date']}_leadership_rotation";write_result(base.with_suffix('.json'),result);atomic_write(base.with_suffix('.csv'),pd.DataFrame(result['candidates']).to_csv(index=False));atomic_write(base.with_suffix('.md'),"# Leadership Rotation\n\n"+"\n".join(f"- #{r['leadership_rank']} {r['sector']} | {r['classification']} | {r['sector_leadership_score']:.1f}" for r in result['candidates'])+"\n");
    for ext in ('.json','.csv','.md'):atomic_write(OUT/f"latest_leadership_rotation{ext}",base.with_suffix(ext).read_text(),backup=False)
    write_record("leadership_rotation",{"module_name":"leadership_rotation","status":result['status'],"freshness":result['freshness'],"generated_at_utc":result['generated_at_utc'],"summary":result['summary'],"top_sectors":result['candidates'][:3],"bottom_sectors":result['candidates'][-3:],"transitions":[r for r in result['candidates'] if r.get('leadership_rank_change')][:5],"risks":result['risks'][:5],"source_file":str(base.with_suffix('.json'))});return result
if __name__=='__main__':print(f"Leadership sectors: {len(run()['candidates'])}")

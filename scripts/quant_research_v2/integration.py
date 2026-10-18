"""Additive canonical integration, independent of scoring and frozen experiments."""
from datetime import datetime,timezone
from .runner import run
from .benchmark_refresh import refresh_hourly_btc
from .lifecycle import MODEL

def extend_handoff(packet, root):
    if packet['run_metadata']['pipeline_status'] not in ('OK','OK_WITH_WARNINGS'):
        packet['V2_RESEARCH']={'status':'SKIPPED_FAILED_UPSTREAM','trading_capability':'DISABLED'}
        return
    try:
        as_of=datetime.now(timezone.utc).isoformat()
        refresh_hourly_btc(root,as_of)
        context=run(root,as_of,capture_current=True,require_benchmark=True)
        packet['V2_RESEARCH']={'status':'OK','schema_version':'1.0.0',
            'timing_basis':'CLOSED_CANDLE_REFERENCE','run_id':context['run_id'],
            'inventory':context['inventory'],'horizon_counts':context['horizon_counts'],
            'lifecycle_model_version':MODEL,'measurement_counts':context['measurement_counts'],
            'benchmark_preflight':context['benchmark_preflight'],
            'compact_handoff':'DAILY_REPORTS/CHATGPT_HANDOFF/latest_quant_research_v2.json',
            'trading_capability':'DISABLED'}
    except Exception as exc:
        # Legacy artifact remains compatible; V2 must fail closed and visible.
        packet['V2_RESEARCH']={'status':'FAILED','error':str(exc),'trading_capability':'DISABLED'}
        packet['run_metadata']['pipeline_status']='FAILED_REQUIRED_DATA'
        failure='V2_MEASUREMENT_FAILED: '+str(exc)
        packet['system_health']['module_failures'].append(failure)
        packet['SYSTEM_HEALTH']['module_failures']=list(packet['system_health']['module_failures'])

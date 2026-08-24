from __future__ import annotations
import argparse,json
from collections import defaultdict,Counter
from pathlib import Path

def compare(dataset:Path,v0_path:Path,v1_path:Path)->dict:
    rows={x['case_id']:x for x in (json.loads(line) for line in dataset.read_text(encoding='utf8').splitlines() if line.strip())}
    v0=json.loads(v0_path.read_text(encoding='utf8')); v1=json.loads(v1_path.read_text(encoding='utf8')); a={x['case_id']:x for x in v0['predictions']}; b={x['case_id']:x for x in v1['predictions']}; transitions=[]; by=defaultdict(lambda:{'count':0,'v0_correct':0,'v1_correct':0,'v0_unsafe':0,'v1_unsafe':0,'v1_reasons':Counter()}); wrong_right=right_wrong=unsafe=false_reject=0
    for cid,row in rows.items():
        pa,pb=a[cid],b[cid]; gold=row['gold_label']; mode='other'
        for name in ('missing_qualifier','wrong_entity','numeric_mismatch','temporal_mismatch','semantic_overlap_but_insufficient','unsupported_risk_inference'):
            if f'failure_mode={name}' in row.get('annotation_notes',''): mode=name; break
        stats=by[mode]; stats['count']+=1; stats['v0_correct']+=pa['predicted_label']==gold; stats['v1_correct']+=pb['predicted_label']==gold; stats['v0_unsafe']+=gold in {'PARTIAL','UNSUPPORTED'} and pa['predicted_label']=='SUPPORTED'; stats['v1_unsafe']+=gold in {'PARTIAL','UNSUPPORTED'} and pb['predicted_label']=='SUPPORTED'; stats['v1_reasons'][pb['reason_code']]+=1
        if pa['predicted_label']!=pb['predicted_label']:
            transitions.append({'case_id':cid,'gold':gold,'v0_prediction':pa['predicted_label'],'v1_prediction':pb['predicted_label'],'v1_feature_result':pb['feature_result'],'reason_code':pb['reason_code'],'failure_type':mode})
        wrong_right+=pa['predicted_label']!=gold and pb['predicted_label']==gold; right_wrong+=pa['predicted_label']==gold and pb['predicted_label']!=gold; unsafe+=gold in {'PARTIAL','UNSUPPORTED'} and pb['predicted_label']=='SUPPORTED'; false_reject+=gold=='SUPPORTED' and pb['predicted_label']!='SUPPORTED'
    failure={k:{**{x:v for x,v in val.items() if x!='v1_reasons'},'v1_reasons':dict(val['v1_reasons']),'improvement':val['v1_correct']-val['v0_correct']} for k,val in by.items()}
    return {'v0_metrics':v0['metrics'],'v1_metrics':v1['metrics'],'transition_count':len(transitions),'v0_wrong_v1_right':wrong_right,'v0_right_v1_wrong':right_wrong,'unsafe_acceptance_count':unsafe,'supported_false_rejection_count':false_reject,'failure_type_comparison':failure,'prediction_transitions':transitions}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--dataset',type=Path,required=True); p.add_argument('--v0',type=Path,required=True); p.add_argument('--v1',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); a.output.write_text(json.dumps(compare(a.dataset,a.v0,a.v1),ensure_ascii=False,indent=2)+'\n',encoding='utf8')

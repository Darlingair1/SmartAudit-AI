from __future__ import annotations
import json
from pathlib import Path

def compare(original:Path,audited:Path,output:Path):
    a=json.loads(original.read_text(encoding='utf8')); b=json.loads(audited.read_text(encoding='utf8')); amap={x['case_id']:x for x in a['predictions']}; bmap={x['case_id']:x for x in b['predictions']}; transitions=[]
    for cid in sorted(amap):
        if amap[cid]['predicted_label']!=bmap[cid]['predicted_label']:
            transitions.append({'case_id':cid,'original':amap[cid]['predicted_label'],'audited':bmap[cid]['predicted_label'],'text_action':next((x.get('text_action') for x in []),None)})
    output.write_text(json.dumps({'original_metrics':a['metrics'],'audited_metrics':b['metrics'],'prediction_transition_count':len(transitions),'prediction_transitions':transitions},ensure_ascii=False,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('--original',type=Path,required=True); p.add_argument('--audited',type=Path,required=True); p.add_argument('--output',type=Path,required=True); x=p.parse_args(); compare(x.original,x.audited,x.output)

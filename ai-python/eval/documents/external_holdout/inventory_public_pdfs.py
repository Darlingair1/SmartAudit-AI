from __future__ import annotations
import hashlib, json, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[4]
PUBLIC=ROOT/'ai-python/eval/documents/public'
OUT=ROOT/'ai-python/eval/documents/external_holdout'
OLD={
 'guangdong_tax_e_tax_development_contract_2023_gpcgd23c500fg157f.pdf':('public_guangdong_tax_e_tax_development_2023_gpcgd23c500fg157f','development'),
 'jiyuan_vehicle_procurement_contract_2024_245_a.pdf':('public_jiyuan_vehicle_procurement_2024_245_a','development'),
 'uk_dwp_dos010_curam_technical_architect_call_off_contract_2017.pdf':('public_uk_dwp_dos010_curam_technical_architect_2017','development'),
}
INFERRED={
 '1746527472741_5024.pdf':{'title':'高速公路门架系统状态监测运维项目合同','publishing_institution':'陕西省高速公路收费中心','provenance_note':'inferred from extracted first-page text; source URL not verified'},
 '8a69c8e290831b250190964f57453e46.pdf':{'title':'2024年城市市政设施维护工程合同','publishing_institution':'西安市市政设施管理中心','provenance_note':'inferred from extracted first-page text; source URL not verified'},
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(t): return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',t or '')).strip()
def inspect(p):
    item={'filename':p.name,'relative_path':p.relative_to(ROOT).as_posix(),'file_size':p.stat().st_size,'sha256':sha(p),'filesystem_mtime':p.stat().st_mtime,'page_count':0,'parse_ok':False,'encrypted':False,'damaged':False,'text_extractable':False,'extracted_text_char_count':0,'normalized_text_sha256':None,'pdf_metadata':{},'text_preview':''}
    try:
        r=PdfReader(str(p),strict=False); item['encrypted']=bool(r.is_encrypted); item['page_count']=len(r.pages); item['pdf_metadata']={str(k):str(v) for k,v in (r.metadata or {}).items()}
        texts=[(page.extract_text() or '') for page in r.pages]; full='\n'.join(texts); n='\n<PageBoundary>\n'.join(norm(x) for x in texts); item.update(parse_ok=True,extracted_text_char_count=len(full),text_extractable=bool(full.strip()),normalized_text_sha256=hashlib.sha256(n.encode('utf8')).hexdigest(),text_preview=norm(full)[:300])
    except Exception as exc: item['damaged']=True; item['error']=str(exc)
    item['historical_status']='KNOWN_DEVELOPMENT' if p.name in OLD else 'CANDIDATE_NEW_BY_INVENTORY_STATE'
    item['historical_document_id']=OLD.get(p.name,(None,None))[0]
    return item
def main():
    OUT.mkdir(parents=True,exist_ok=True); items=[inspect(p) for p in sorted(PUBLIC.rglob('*.pdf'))]
    by_name={x['filename']:x for x in items}
    exclusion_details=[]
    for filename,(doc_id,status) in OLD.items():
        x=by_name[filename]
        exclusion_details.append({'filename':filename,'document_id':doc_id,'status':status,'sha256':x['sha256'],'normalized_text_sha256':x['normalized_text_sha256'],'supporting_repository_paths':['ai-python/eval/datasets/rag_eval_dev_v1.jsonl','ai-python/eval/judge/claim_evidence_benchmark_v1.jsonl','ai-python/eval/judge/claim_evidence_generalization_v1.jsonl']})
    for x in items:
        if x['historical_status']!='CANDIDATE_NEW_BY_INVENTORY_STATE': continue
        x['near_duplicate_comparisons']=[]
        for old in exclusion_details:
            prior=by_name[old['filename']]
            x['near_duplicate_comparisons'].append({'historical_filename':old['filename'],'normalized_text_hash_equal':x['normalized_text_sha256']==prior['normalized_text_sha256'],'preview_similarity':round(SequenceMatcher(None,x['text_preview'],prior['text_preview']).ratio(),6)})
    hashes={};
    for x in items: hashes.setdefault(x['sha256'],[]).append(x['filename'])
    for x in items: x['exact_duplicate_files']=hashes[x['sha256']]
    (OUT/'candidate_inventory.json').write_text(json.dumps({'schema_version':'public_pdf_inventory_v1','root':'ai-python/eval/documents/public','pdf_count':len(items),'historical_exclusion_set':exclusion_details,'items':items},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    candidates=[x for x in items if x['historical_status']=='CANDIDATE_NEW_BY_INVENTORY_STATE']
    manifest=[]
    for x in candidates:
        reasons=[]; qualification='ELIGIBLE'
        if not x['parse_ok'] or x['damaged']: qualification='EXCLUDE'; reasons.append('PDF_INVALID')
        elif not x['text_extractable']: qualification='NEEDS_MANUAL_REVIEW'; reasons.append('TEXT_EXTRACTION_REQUIRES_OCR')
        elif x['file_size']==0 or x['page_count']<=0: qualification='EXCLUDE'; reasons.append('PDF_INVALID')
        if not x['pdf_metadata']: reasons.append('PDF_METADATA_UNAVAILABLE')
        reasons.append('SOURCE_URL_MISSING')
        near_equal=any(y['normalized_text_hash_equal'] for y in x.get('near_duplicate_comparisons',[]))
        if near_equal: qualification='NEEDS_MANUAL_REVIEW'; reasons.append('SAME_DOCUMENT_NEAR_DUPLICATE')
        if qualification=='ELIGIBLE': qualification='NEEDS_MANUAL_REVIEW'
        inferred=INFERRED.get(x['filename'],{}); manifest.append({k:x.get(k) for k in ('filename','relative_path','sha256','normalized_text_sha256','page_count','file_size') } | {'title':inferred.get('title') or x['pdf_metadata'].get('/Title'),'publishing_institution':inferred.get('publishing_institution'),'source_url':None,'provenance_note':inferred.get('provenance_note'),'historical_duplicate':False,'near_duplicate_status':'POSSIBLE' if near_equal else 'NO_EXACT_NORMALIZED_MATCH','qualification':qualification,'reason_codes':reasons})
    (OUT/'candidate_manifest.json').write_text(json.dumps({'schema_version':'external_holdout_candidate_manifest_v1','candidate_count':len(manifest),'candidates':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'pdf_count':len(items),'candidate_count':len(candidates),'candidates':[x['filename'] for x in candidates]},ensure_ascii=False,indent=2))
if __name__=='__main__': main()

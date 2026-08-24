from __future__ import annotations
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
manifest=ROOT/'ai-python/eval/documents/external_holdout/candidate_manifest.json'
inventory=json.loads((ROOT/'ai-python/eval/documents/external_holdout/candidate_inventory.json').read_text(encoding='utf8'))
items={x['filename']:x for x in inventory['items']}
confirmed={
 '1746527472741_5024.pdf':{'title':'高速公路门架系统状态监测运维项目合同','publishing_institution':'陕西省高速公路收费中心','purchaser':'陕西省高速公路收费中心','project_no':'SFZXXJ-2024-03','contract_no':None,'contract_no_note':'原合同 PDF 首部编号无法可靠解析，不得猜测','source_description':'陕西省官方政府/交通运输系统来源','text_source':'native','ocr_quality_status':'NOT_APPLICABLE'},
 '1749525786473_9685.pdf':{'title':'建设工程委托监理合同长安区杜曲街道初级中学新建教学综合楼项目','publishing_institution':'西安市长安区杜曲街道初级中学','purchaser':'西安市长安区杜曲街道初级中学','project_no':'ZCBN-长安区-2025-00156','contract_no':'HT-长安区-2025-00091','text_source':'ocr','ocr_quality_status':'OCR_ENGINE_UNAVAILABLE'},
 '1750995540261_9.pdf':{'title':'技术服务合同','project':'镇巴县月滩河、渚河、泾洋河、渔水河、铁溪河、毛家河河流防御洪水预案及镇巴县县城防洪应急预案项目','publishing_institution':'镇巴县水利局','purchaser':'镇巴县水利局','project_no':'ZCBN-镇巴县-2025-00216','contract_no':'HT-镇巴县-2025-00055','text_source':'ocr','ocr_quality_status':'OCR_ENGINE_UNAVAILABLE'},
 '402881d28f394a24018f4e2453c9348d.pdf':{'title':'财政业务系统运维及技术支持服务合同包2（国库集中支付电子化系统运维及技术支持服务）','publishing_institution':'赤峰市公共财政保障中心','purchaser':'赤峰市公共财政保障中心','project_no':'2024CG001FW-2','contract_no':'2024CG001FW-002','text_source':'ocr','ocr_quality_status':'OCR_ENGINE_UNAVAILABLE'},
 '8a69c8e290831b250190964f57453e46.pdf':{'title':'2024年城市市政设施维护工程合同（第2标包）','publishing_institution':'西安市市政设施管理中心','purchaser':'西安市市政设施管理中心','contractor':'西安市东郊市政设施养护管理有限公司','contract_no':None,'contract_no_note':'原 PDF 合同编号栏为空，不得猜测','text_source':'native','ocr_quality_status':'NOT_APPLICABLE'},
}
out=[]
for row in json.loads(manifest.read_text(encoding='utf8'))['candidates']:
    extra=confirmed[row['filename']]; item=items[row['filename']]
    row.update(extra)
    row['source_url']=None
    row['source_provenance_status']='CONFIRMED_BY_HUMAN_MAPPING_SOURCE_URL_NOT_PROVIDED'
    row['original_sha256']=item['sha256']
    row['derived_text_sha256']=item['normalized_text_sha256'] if extra['text_source']=='native' else None
    row['ocr_engine']=None if extra['text_source']=='native' else 'UNAVAILABLE_IN_CURRENT_ENVIRONMENT'
    row['ocr_engine_version']=None
    row['ocr_config']=None if extra['text_source']=='native' else {'required':True,'performed':False,'reason':'No OCR engine or PDF rendering dependency installed'}
    row['ocr_text_sha256']=None
    row['qualification']='NEEDS_MANUAL_REVIEW'
    reasons=list(dict.fromkeys(row.get('reason_codes',[])))
    if extra['text_source']=='ocr': reasons.extend(['TEXT_EXTRACTION_REQUIRES_OCR','OCR_ENGINE_UNAVAILABLE'])
    reasons.append('SOURCE_URL_MISSING')
    row['reason_codes']=list(dict.fromkeys(reasons))
    row['near_duplicate_status']='NO_EXACT_NORMALIZED_MATCH'
    row['historical_duplicate']=False
    out.append(row)
manifest.write_text(json.dumps({'schema_version':'external_holdout_candidate_manifest_v1','candidate_count':len(out),'provenance_review':'human_confirmed_mapping_applied','ocr_policy':'Original PDFs unchanged; OCR derived artifacts absent because engine unavailable; no OCR text fabricated','candidates':out},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'candidate_count':len(out),'original_hashes_unchanged':all(x['original_sha256']==items[x['filename']]['sha256'] for x in out)},ensure_ascii=False,indent=2))

import hashlib,json
from pathlib import Path
from eval.judge.validate_external_holdout import validate

def fixture(tmp_path:Path,document_id="external_public_contract_001"):
    doc=tmp_path/"contract.txt"; doc.write_text("公开合同文本",encoding="utf8")
    row={"case_id":"external_001","document_id":document_id,"risk_type":"PAYMENT_TERM","claim":"付款条件是什么？","evidence":[{"evidence_id":"run-1:c-1","text":"验收后支付价款。","page":1}],"gold_label":"SUPPORTED","review_status":"reviewed","annotation_notes":"Independent human evidence-sufficiency review.","challenge_tags":["paraphrase"],"source_pipeline_provenance":{"pipeline_run_id":"run-1","claim_source":"smartaudit_risk_output","retrieval_source":"smartaudit_retrieval_output"},"initial_label":"SUPPORTED","adjudicated_label":"SUPPORTED","adjudication_notes":"Confirmed independently.","label_confidence":"high"}
    data=tmp_path/"data.jsonl"; data.write_text(json.dumps(row,ensure_ascii=False)+"\n",encoding="utf8"); digest=hashlib.sha256(data.read_bytes()).hexdigest()
    meta={"dataset_sha256":digest,"source_documents":[{"document_id":document_id,"repository_path":"contract.txt","document_hash":hashlib.sha256(doc.read_bytes()).hexdigest()}],"reviewed_count":1,"draft_count":0,"unresolved_count":0,"label_distribution":{"SUPPORTED":1},"document_distribution":{document_id:1},"challenge_type_distribution":{"paraphrase":1},"adjudication_status":"complete"}
    metadata=tmp_path/"metadata.json"; metadata.write_text(json.dumps(meta),encoding="utf8"); return data,metadata

def test_valid_external_holdout(tmp_path):
    data,meta=fixture(tmp_path); assert validate(data,meta,tmp_path)["status"]=="valid"

def test_development_document_is_rejected(tmp_path):
    data,meta=fixture(tmp_path,"synthetic_purchase_contract_001"); result=validate(data,meta,tmp_path); assert result["status"]=="invalid"; assert any("development document" in x for x in result["errors"])

def test_draft_or_controlled_perturbation_is_rejected(tmp_path):
    data,meta=fixture(tmp_path); row=json.loads(data.read_text(encoding="utf8")); row["review_status"]="draft"; row["source_pipeline_provenance"]["construction"]="controlled_perturbation"; data.write_text(json.dumps(row)+"\n",encoding="utf8"); result=validate(data,meta,tmp_path); assert result["status"]=="invalid"; assert any("controlled perturbation" in x for x in result["errors"])

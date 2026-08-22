# DOS_010 Retrieval Candidate 人工审核单

## 文档信息

- Document ID: `public_uk_dwp_dos010_curam_technical_architect_2017`
- 文件: `eval/documents/public/uk_dwp_dos010_curam_technical_architect_call_off_contract_2017.pdf`
- Physical pages: 41
- Canonical extraction: Python 3.11.5 / pypdf 6.14.2
- Document SHA256: `dd1f1e1da81075a1fb9f40d313f2c531ad9b7da9b61f4defb36d0a8c7fe9760b`
- Extraction SHA256: `148357ca818fc3972ba37a4312da34e05323e614210b4c573e659baaf38aed34`
- 当前状态: 人工审核完成；q001-q008 均批准为 `reviewed`
- 审核决定记录日期: 2026-08-22

## 最终审核决定

- q001: 修改 Query；移除非必要的 latest-extension-date 方向；新增 page 13
  Schedule 3.5 中 Supplier prior written approval Gold。
- q002: 原 Query、Gold、type 和 difficulty 通过。
- q003: Query 改为 `When may the Supplier invoice monthly, and what must the
  Buyer first accept?`
- q004: 原 Query、Gold、type 和 difficulty 通过。
- q005: Query 改为明确区分依法披露与因 breach 成为 public 的否定例外。
- q006: Query 改为明确两工作日是 Supplier transfer deadline，不要求合同外
  FOIA/EIR 法定期限知识。
- q007: Query 改为适用于 any expiry or termination；新增 page 29 clause 23.3
  的 partial-day/full-Working-Day 计算规则。
- q008: Query 将 regulatory losses/fines 明确限定为 Supplier's breach of Law。

以上修改后的 8 个 case 均获准写入 `rag_eval_dev_v1.jsonl`，状态为
`annotation_status = reviewed`。没有 `reserve` 或 `reject` case。

## Post-evaluation Adjudication

人工随后选择了 q001 equivalent-evidence 裁决的 Option A：

- 原 q001 被拆分；当前 q001 仅询问 Order Form 的起止日期、最大可选延长期和
  notice period，Gold 仅为 physical page 2 的三个字段，difficulty 为 medium。
- 新增 q009 询问延期通知内容和 Supplier prior written approval，Gold 位于
  physical pages 13/18，difficulty 为 hard。
- q001 和 q009 均为 `reviewed`。历史 evaluation report 保留拆分前结果，不作
  追溯改写。

## 审核原则

对每个 case 请确认：

- [ ] Query 是自然的检索问题，不依赖合同外知识。
- [ ] Query 没有泄露页码、条款号或过多答案数字。
- [ ] 每段 Gold 都是回答 Query 必需的最小证据。
- [ ] Gold 原文和 physical page 正确。
- [ ] 没有遗漏必要条件、例外或第二段合理 Gold。
- [ ] `multiple_evidence` 的每段 Gold 都确实必要。
- [ ] difficulty 和 case type 合理。
- [ ] 最终决定明确为 `reviewed`、`reserve/draft` 或 `reject`。

PDF 特有检查：

- [ ] 接受 production canonical extraction 中的换行、空格和连字符形式。
- [ ] 跨页规则已拆成 page-local Gold，没有把跨页文本错误标为单页。
- [ ] 重复页眉/页脚未被选入 Gold。
- [ ] `[REDACTED]` 内容未被用作 Gold。

## 决策总表

| Case | 建议类型 | 建议难度 | 重点判断 | 人工决定 |
|---|---|---:|---|---|
| q001 | multiple_evidence / long_distance / numeric_confusion | hard | Query 是否同时要求最晚结束日期 | 待填写 |
| q002 | multiple_evidence / numeric_confusion | medium | 详细累计值是否应优先于首页摘要值 | 待填写 |
| q003 | single_evidence | easy | “monthly payment”是否会被误解为付款期限 | 待填写 |
| q004 | single_evidence / hard_negative | medium | capped/fixed price 的适用条件是否表达充分 | 待填写 |
| q005 | multiple_evidence / negation / hard_negative | hard | 反事实否定问法是否自然 | 待填写 |
| q006 | multiple_evidence / numeric_confusion | medium | 不应要求回答合同外 FOIA 法定期限 | 待填写 |
| q007 | multiple_evidence / long_distance / hard_negative | hard | 数据销毁规则适用于所有终止/届满 | 待填写 |
| q008 | multiple_evidence / long_distance / hard_negative | hard | regulatory loss 必须限定为 breach of Law | 待填写 |

---

## q001

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_001`

**Proposed Query:**

> What are the initial contract dates and maximum extension, and what must the Buyer do to exercise the extension?

**Proposed Type:** `multiple_evidence`, `long_distance`, `numeric_confusion`  
**Proposed Difficulty:** `hard`

**Proposed Gold:**

Physical page 2:

```text
Start date  29th August 2017
End date 22nd December 2017
```

Physical page 2:

```text
(Optional) Maximum Call-
Off Contract Extension
Period
24 Working Days
```

Physical page 2:

```text
Notice period (prior to the
initial Call-Off Contract
period) to trigger Call-Off
Contract Extension
15 calendar days
```

Physical page 18:

```text
an Extension Period was specified in the Order Form
```

Physical page 18:

```text
written notice was given to the Supplier before the expiry of the notice period set out in the
Order Form.
```

Physical page 18:

```text
The notice must state that the Call-Off Contract term will be extended, and must
specify the number of whole days of the extension.
```

Physical page 13:

```text
obtain prior written
approval from the Supplier before applying any Extension Period to  the Call -Off Contract period.
```

**定位诊断:** Parents `p-0002 + p-0018`; 6 Gold / 3 distinct children / 2 distinct parents。

**需要判断:**

- [ ] “maximum extension”只要求最大延长天数，还是也应回答 Order Form 中的 latest extension end date？
- [ ] 初始 start/end dates 是否确有必要，还是 Query 应缩小为延期机制？
- [ ] 六段 Gold 是否保持最小且全部必要？
- [ ] 接受当前 hard 难度。

**主要 hard negative:** initial end date、latest extension end date、early termination date 都包含结束日期，但法律/业务效果不同。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## q002

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_002`

**Proposed Query:**

> What is the maximum cumulative Call-Off Contract value, and does it commit the Buyer to any minimum spend?

**Proposed Type:** `multiple_evidence`, `numeric_confusion`  
**Proposed Difficulty:** `medium`

**Proposed Gold, physical page 4:**

```text
Call-Off Contract value: The maximum cumulative values of the SoW’s that may be executed under
this Call-Off Contract at the discretion of the Buyer (DWP) shall be a maximum
of £137,229.40 (inc any expense amount) exclusive of VAT.
```

```text
this agreement places “no minimum commitment of spend” obligations
on the Buyer;
```

**定位诊断:** Parent `p-0004`; 2 Gold / 2 distinct children。

**需要判断:**

- [ ] Gold 1 应使用详细条款，而不是首页只有金额的摘要字段。
- [ ] “maximum cumulative”足以区分 overall Call-Off value 与 individual SOW value。
- [ ] no minimum commitment 的否定证据不可省略。

**主要 hard negative:** individual SOW maximum contracted value 和首页 Call-Off Contract value。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## q003

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_003`

**Proposed Query:**

> When are invoices submitted and what must the Buyer have accepted before monthly payment?

**Proposed Type:** `single_evidence`  
**Proposed Difficulty:** `easy`

**Proposed Gold, physical page 4:**

```text
Invoice frequency Monthly in arrears upon acceptance from the Buyer of valid submitted
timesheets and any associated costs.
```

**定位诊断:** Parent `p-0004`; Child `c-0004-0024`。

**需要判断:**

- [ ] “before monthly payment”是否会被误解为付款截止日期。
- [ ] 是否改为 “When may the Supplier invoice monthly, and what must the Buyer first accept?” 更准确。
- [ ] 保留为 easy、single evidence。

**主要 hard negative:** invoice required fields、BACS payment method、general payment/VAT provisions。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## q004

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_004`

**Proposed Query:**

> If a SOW has a capped or fixed price and that price is exceeded, who bears the excess cost?

**Proposed Type:** `single_evidence`, `hard_negative`  
**Proposed Difficulty:** `medium`

**Proposed Gold, physical page 12:**

```text
3.4.3 If a capped or fixed price has been agreed for a SOW:
● The Supplier will continue at its own cost and expense to provide the Services even where the
agreed price has been exceeded; and
● The Buyer will have no obligation or liability to pay for the cost of any Services delivered relating
to this order after the agreed price has been exceeded.
```

**定位诊断:** Parent `p-0012`; Child `c-0012-0078`。

**需要判断:**

- [ ] Query 已明确 capped/fixed price 条件，不会被误用于 Time and Materials。
- [ ] 两个 bullet 应作为一条完整 Gold，而不是拆成两条 Gold。
- [ ] `hard_negative` 标签成立，但难度保持 medium。

**主要 hard negative:** clauses 3.4.1-3.4.2 的 Time and Materials、rates、expenses 和 contingency margin。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## q005

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_005`

**Proposed Query:**

> May confidential information be disclosed to meet legal obligations or when it becomes public through breach, and which Supplier Staff may receive Buyer information?

**Proposed Type:** `multiple_evidence`, `negation`, `hard_negative`  
**Proposed Difficulty:** `hard`

**Proposed Gold:**

Physical page 21:

```text
● must be disclosed to comply with legal obligations placed on the Party making the disclosure
```

Physical page 21:

```text
● is, or becomes, public knowledge, other than by breach of this Clause or the Call -Off
Contract
```

Physical page 22:

```text
11.5  The Supplier may only disclose the Buyer’s Confidential Information to Supplier Staff who are
directly involved in the provision of the Services and who need to know the information to provide the
Services. The Supplier will ensure that its Supplier Staff will comply with these obligations.
```

**定位诊断:** Parents `p-0021 + p-0022`; 3 Gold / 3 distinct children / 2 distinct parents。

**需要判断:**

- [ ] “when it becomes public through breach”这种反事实否定问法是否自然、无歧义。
- [ ] 是否应改为 “Does information becoming public through a breach permit disclosure?”
- [ ] legal obligation、public knowledge exception 和 Supplier Staff restriction 是否适合放在同一个 Query。
- [ ] 三段 Gold 是否真的全部必要，而不是两个可拆分 case。

**主要 hard negative:** Buyer-specific disclosure rights、prior written consent、FOI rules。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## q006

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_006`

**Proposed Query:**

> What must the Supplier do after receiving a Freedom of Information request, and within what time?

**Proposed Type:** `multiple_evidence`, `numeric_confusion`  
**Proposed Difficulty:** `medium`

**Proposed Gold, physical page 26:**

```text
18.1  The Supplier will transfer any Request for Information to the Buyer within 2 Working Days of receipt.
```

```text
18.2  The Supplier will provide all necessary help reasonably requested by the Buyer to enable  the Buyer
to respond to the Request for Information within the time for compliance set out in section 10 of the Freedom
of Information Act or Regulation 5 of the Environmental Information Regulations.
```

**定位诊断:** Parent `p-0026`; 2 Gold / 2 distinct children。

**需要判断:**

- [ ] Query 中 “within what time”只指 Supplier 两工作日转交期限。
- [ ] 不要求标注者或被测系统从合同外推导 FOIA/EIR 的法定答复期限。
- [ ] 第二段合理协助义务对完整回答是必要 Gold。

**主要 hard negative:** confidentiality exceptions、data-protection notification duties。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## q007

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_007`

**Proposed Query:**

> How is the Buyer’s minimum notice for convenience termination calculated, and when and how must Buyer Data be destroyed afterward?

**Proposed Type:** `multiple_evidence`, `long_distance`, `hard_negative`  
**Proposed Difficulty:** `hard`

**Proposed Gold:**

Physical page 29:

```text
23.2  The minimum notice period (expressed in Working Days) to be given by the Buyer to terminate
under this Clause will be the number of whole days that represent 20% of the total duration of the current
SOW to be performed under the Call-Off Contract
```

Physical page 29:

```text
up to a maximum of 30 Working Days.
```

Physical page 29:

```text
23.3  Partial days will be discounted in the calculation and the duration of the SOW will be calculated in full
Working Days.
```

Physical page 30:

```text
destroy all copies of the Buyer Data when they receive the Buyer’s written
instructions to do so
```

Physical page 30:

```text
12 months after the date of expiry or termination (whichever is the earlier)
```

Physical page 30:

```text
provide written confirmation to the Buyer that the data has been destroyed, except where the
retention of Buyer Data is required by Law
```

**定位诊断:** Parents `p-0029 + p-0030`; 5 Gold / 4 distinct children / 2 distinct parents。

**需要判断:**

- [ ] “afterward”是否会错误暗示数据销毁规则只适用于 convenience termination。
- [ ] 是否改为明确询问 “After expiry or termination...” 的通用处置规则。
- [ ] Query 是否还需要询问先行返还/移交数据；若不需要，不应扩大 Gold。
- [ ] 五段 Gold 均为完整回答所必需。

**主要 hard negative:** immediate termination for default/fraud、Material Breach、Force Majeure，以及 data return/transfer 条款。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## q008

**Case ID:** `public_uk_dwp_dos010_curam_technical_architect_2017_q_008`

**Proposed Query:**

> Which Supplier indemnities are unlimited, and are regulatory fines caused by breach treated as recoverable direct loss?

**Proposed Type:** `multiple_evidence`, `long_distance`, `hard_negative`  
**Proposed Difficulty:** `hard`

**Proposed Gold:**

Physical page 32:

```text
34.2  In respect of the indemnities in Clause 13 (Intellectual Property Rights) and Clause 28 (Staff
Transfer) the Supplier’s total liability will be unlimited. Buyers are not limited in the number of times they can
call on this indemnity.
```

Physical page 33:

```text
34.5  The Supplier will be liable for the following types of loss which will be regarded as direct and will be
recoverable by the Buyer:
```

Physical page 33:

```text
any regulatory losses, fines, expenses or other losses arising from a breach by the Supplier
of any Law.
```

**定位诊断:** Parents `p-0032 + p-0033`; 3 Gold / 3 distinct children / 2 distinct parents。

**需要判断:**

- [ ] Query 应明确 regulatory fines 来自 Supplier breach of Law，而不是任意合同违约。
- [ ] Gold 2 是解释 Gold 3 被视为 direct/recoverable 所必需的上下文。
- [ ] unlimited indemnities 与 regulatory losses 适合放入同一个 multi-evidence Query。
- [ ] 保持 hard 难度。

**主要 hard negative:** clauses 34.3-34.4 的一般责任限额和间接损失排除。

**人工决定:** `reviewed`  
**最终 Query 修改:**  
**Gold 增删或顺序调整:**  
**备注:**

---

## 审核完成后的执行 Gate

只有以下项目全部完成后，才能正式写入 benchmark：

- [ ] 每个拟纳入 case 都有明确的最终 Query。
- [ ] 每个拟纳入 case 的 Gold 集合和顺序已确认。
- [ ] 每个拟纳入 case 的 difficulty/type 已确认。
- [ ] 拟纳入 case 标记为 `reviewed`；未纳入项保持 `draft/reserve`。
- [ ] 同意将本文档的人工决定作为 dataset 更新依据。

审核通过后的下一阶段依次为：更新 manifest、写入 reviewed cases、运行
`validate_benchmark`、在 validator PASS 后运行 current production Retrieval
Evaluation。任何 validator localization 失败都必须停止，不得为了通过验证修改
Gold 或 production retrieval。

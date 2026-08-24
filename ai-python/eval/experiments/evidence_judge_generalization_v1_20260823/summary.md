# Evidence Judge Generalization v1 (blind)

Dataset SHA256: `8b171081aa27a07e7e4d9d0b4ccc8de75e28926aa582822a04985182b7831d8e`
Samples: 107

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.383178 |
| macro_f1 | 0.270165 |
| supported_precision | 0.800000 |
| unsupported_recall | 0.900000 |
| unsafe_acceptance_rate | 0.014925 |
| human_review_rate | 0.186916 |
| automation_coverage | 0.813084 |

## Naturalistic Challenge Types

| Type | Count | Accuracy |
|---|---:|---:|
| chinese_numeral_or_amount | 7 | 0.285714 |
| complex_negation_exception | 6 | 0.000000 |
| conflicting_evidence | 16 | 0.875000 |
| cross_sentence_qualifier | 7 | 0.000000 |
| implicit_entity_coreference | 7 | 0.142857 |
| implicit_risk_inference | 6 | 0.000000 |
| multi_evidence_support | 27 | 0.037037 |
| paraphrase_synonym | 7 | 0.142857 |
| semantically_related_but_insufficient | 24 | 0.916667 |

Errors: 66

## Blind Failure Analysis

- `naturalistic_001_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=paraphrase_synonym
- `naturalistic_002_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=implicit_entity_coreference
- `naturalistic_003_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=chinese_numeral_or_amount
- `naturalistic_003_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_004_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=cross_sentence_qualifier
- `naturalistic_004_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_005_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=complex_negation_exception
- `naturalistic_005_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_006_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=implicit_risk_inference
- `naturalistic_007_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=paraphrase_synonym
- `naturalistic_008_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=implicit_entity_coreference
- `naturalistic_008_partial` gold=PARTIAL predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=multi_evidence_support
- `naturalistic_009_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=NUMERIC_MISMATCH type=chinese_numeral_or_amount
- `naturalistic_009_partial` gold=PARTIAL predicted=UNSUPPORTED reason=NUMERIC_MISMATCH type=multi_evidence_support
- `naturalistic_010_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=cross_sentence_qualifier
- `naturalistic_011_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=complex_negation_exception
- `naturalistic_012_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=implicit_risk_inference
- `naturalistic_013_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=paraphrase_synonym
- `naturalistic_013_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_014_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=implicit_entity_coreference
- `naturalistic_014_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_015_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=chinese_numeral_or_amount
- `naturalistic_015_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_016_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=cross_sentence_qualifier
- `naturalistic_016_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_017_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=complex_negation_exception
- `naturalistic_017_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_018_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=implicit_risk_inference
- `naturalistic_018_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_019_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=paraphrase_synonym
- `naturalistic_020_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=implicit_entity_coreference
- `naturalistic_020_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_021_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=chinese_numeral_or_amount
- `naturalistic_022_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=cross_sentence_qualifier
- `naturalistic_022_partial` gold=PARTIAL predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=multi_evidence_support
- `naturalistic_023_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=complex_negation_exception
- `naturalistic_023_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_024_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=implicit_risk_inference
- `naturalistic_024_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_025_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=paraphrase_synonym
- `naturalistic_025_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_026_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=implicit_entity_coreference
- `naturalistic_027_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=chinese_numeral_or_amount
- `naturalistic_027_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_028_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=cross_sentence_qualifier
- `naturalistic_028_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_029_supported` gold=SUPPORTED predicted=PARTIAL reason=STRUCTURED_SIGNALS_INSUFFICIENT type=complex_negation_exception
- `naturalistic_030_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=implicit_risk_inference
- `naturalistic_030_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_031_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=paraphrase_synonym
- `naturalistic_031_partial` gold=PARTIAL predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=multi_evidence_support
- `naturalistic_032_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=implicit_entity_coreference
- `naturalistic_032_partial` gold=PARTIAL predicted=UNSUPPORTED reason=LEXICAL_INSUFFICIENT type=multi_evidence_support
- `naturalistic_033_partial` gold=PARTIAL predicted=SUPPORTED reason=ALL_AVAILABLE_CHECKS_PASS type=multi_evidence_support
- `naturalistic_034_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=cross_sentence_qualifier
- `naturalistic_034_unsupported` gold=UNSUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=conflicting_evidence
- `naturalistic_035_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=complex_negation_exception
- `naturalistic_036_supported` gold=SUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=implicit_risk_inference
- `naturalistic_036_partial` gold=PARTIAL predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=multi_evidence_support
- `naturalistic_036_unsupported` gold=UNSUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=semantically_related_but_insufficient
- `naturalistic_038_partial` gold=PARTIAL predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=multi_evidence_support
- `naturalistic_038_unsupported` gold=UNSUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=semantically_related_but_insufficient
- `naturalistic_039_partial` gold=PARTIAL predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=multi_evidence_support
- `naturalistic_039_unsupported` gold=UNSUPPORTED predicted=PARTIAL reason=LEXICAL_WEAK type=conflicting_evidence
- `naturalistic_040_supported` gold=SUPPORTED predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=cross_sentence_qualifier
- `naturalistic_040_partial` gold=PARTIAL predicted=UNSUPPORTED reason=ENTITY_MISMATCH type=multi_evidence_support

Controlled benchmark v1 metrics remain separate and are referenced without aggregation.
No Judge v2 changes were implemented.

## Controlled Benchmark (reported separately)

The frozen controlled Benchmark V1 remains at Accuracy 1.000000 and Macro-F1
1.000000 on 120 samples. These values are not pooled with the naturalistic
challenge metrics above.

## Judge v2 hypotheses (not implemented)

- Separate question/claim intent normalization from evidence consistency so a
  natural user question is not rejected solely for low token overlap.
- Represent multiple evidence spans explicitly and aggregate coverage before
  deciding PARTIAL versus UNSUPPORTED.
- Resolve party references and aliases within the local evidence context before
  applying strict entity mismatch checks.
- Normalize Chinese textual numbers and amounts alongside Arabic numerals,
  while preserving currencies and units.
- Model exception scope across sentence boundaries and distinguish a missing
  condition from direct contradiction.

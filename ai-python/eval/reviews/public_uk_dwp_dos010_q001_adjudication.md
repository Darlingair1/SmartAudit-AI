# DOS_010 q001 Equivalent Evidence Adjudication

## Why A Decision Is Required

The current q001 asks for both contract dates/maximum extension and the steps
needed to apply the extension. Its reviewed Gold uses:

- physical page 2 for initial dates, maximum extension, and notice period;
- physical page 13 for prior written Supplier approval;
- physical page 18 for the extension notice requirements.

The evaluation retrieved physical page 3 at rank 1. Page 3 contains another
contract-valid statement of the commencement date and maximum extension. It can
answer part of the natural Query, but it is not one of the reviewed Gold items.
The matcher correctly rejected it because physical page 3 is not physical page
2. This is not a page-mapping bug.

## Important Schema Constraint

Every item in `expected_evidence` currently means required evidence. Adding the
page 3 statement as one more ordinary item would make both page 2 and page 3
mandatory and would lower recall for a retriever that returns either valid
alternative. Therefore page 3 must not be appended as ordinary Gold.

## Option A - Split And Anchor The Cases (Recommended)

Replace q001 with two independently reviewed cases in a future annotation-only
revision:

1. An Order Form case asking for the initial start/end dates, maximum optional
   extension, and required notice period. Its Query must explicitly say
   `According to the Order Form` so physical page 2 is the intended source and
   page 3 becomes a related but non-responsive section.
2. An extension-procedure case asking what the Buyer must put in its notice and
   what approval is required. Its Gold remains on physical pages 13 and 18.

Advantages:

- works with the current schema and metrics;
- separates numeric confusion from long-distance procedural evidence;
- makes each Gold set semantically necessary;
- does not require retrieval framework changes.

Risk: anchoring the Query to a named document section slightly reduces natural
language ambiguity, although it does not reveal a page or clause number.

## Option B - Add Alternative Evidence Groups

Design a future schema where a semantic fact can be satisfied by any one of
several page-local excerpts, while other facts remain required. This would
represent page 2 OR page 3 correctly.

Advantages:

- preserves the broad natural Query;
- models duplicate contract statements accurately.

Risks:

- requires changes to schema, validator, matcher, metrics, report format, and
  regression tests;
- is outside the current annotation-only scope;
- requires a clear policy for contradictory alternatives and partial recall.

## Option C - Keep q001 As A Diagnostic Case

Leave q001 unchanged and retain its current result only in the diagnostic
candidate baseline. Do not use it as a formal regression-gate case.

This preserves the audit trail but knowingly leaves valid alternative evidence
uncredited by the metric.

## Rejected Approach

Do not replace page 2 with page 3 or append page 3 merely because it ranked
first. Either action would tune Gold after observing retrieval and would not
solve the underlying duplicate-evidence semantics.

## Human Decision

- [x] Option A: split and anchor the cases.
- [ ] Option B: authorize alternative-evidence schema design as a separate task.
- [ ] Option C: keep q001 diagnostic-only and exclude it from any formal gate.

Decision recorded: Option A was approved and implemented.

- q001 now asks specifically for the Order Form dates, maximum optional
  extension, and notice period. It retains only the three physical-page-2 Gold
  items and is `reviewed`, `medium`, `multiple_evidence + numeric_confusion`.
- q009 now asks for the extension notice contents and prior written approval.
  It uses the reviewed physical-page-18 and physical-page-13 Gold items and is
  `reviewed`, `hard`, `multiple_evidence + long_distance + hard_negative`.
- The historical 39-case diagnostic lock and report were not rewritten. They
  continue to describe the pre-adjudication q001 snapshot.

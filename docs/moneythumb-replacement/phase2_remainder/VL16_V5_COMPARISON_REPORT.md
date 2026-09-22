# PaddleOCR-VL-1.6 versus PP-OCRv5

Bounded research comparison completed and independently reviewed 2026-09-16.

## Decision

**Recommendation: investigate VL further in a separately reviewed research step; retain PP-OCRv5 in production.** This experiment does not establish that either model is broadly more accurate on bank statements.

VL shows a favorable synthetic signal and one repeatable exact-amount improvement in the common measurable development sample. The common amount denominator is only one, and VL’s region output cannot feed the current word-based reconstruction contract without additional design. Four VL polygon refusals, one missing transport response, two v5 adapter refusals across passes, missing mixed-statement pairs and partial labels limit the comparison.

The bounded schedule and offline scoring are complete. This is completion with explicit missing measurements, not a clean success for every request. There is no production switch or admitted coverage gain. Phase 2.4 has not started, and the reserved unseen batch remains sealed.

## Experiment

This is the bounded comparison approved in §G.2.3A. Selection, images, references and measurement rules were frozen before development outcomes. Existing archive studies were retained.

The selection rule chose two documents from each combination of digital/scanned/mixed modality and existing v5 evidence/documented extraction problem. Hash ordering selected 12 documents and 33 pages, with a maximum of five pages per document. Of 937 development metadata identities, 449 met those eligibility rules; 472 exceeded the page limit and 16 lacked required metadata. Missing v5 evidence was not treated as an OCR accuracy failure.

Two visual reviews agreed that seven documents, covering 27 pages, were statements. Five documents, covering six pages, were non-statements and were excluded from sending. No excluded member was replaced.

| Selection stratum | Selected documents | Statement-eligible documents | Fresh paired documents |
|---|---:|---:|---:|
| Digital, prior evidence | 2 | 2 | 1 |
| Digital, prior extraction problem | 2 | 1 | 0 |
| Scanned, prior evidence | 2 | 2 | 1 |
| Scanned, prior extraction problem | 2 | 2 | 1 |
| Mixed, prior evidence | 2 | 0 | 0 |
| Mixed, prior extraction problem | 2 | 0 | 0 |

The fresh paired sample is three documents and 13 pages: five digital and eight scanned pages. There are no eligible mixed-document pairs. The other 14 VL first-pass pages have no fresh paired v5 reading in this experiment. These sample limits prevent a broad model ranking.

The frozen schedule contains 84 page slots. All 66 eligible slots now have a disposition, with 65 retained responses and 59 admitted page observations. After the statement gate, those 66 slots comprise: 13 v5 first-pass pages, 27 VL first-pass pages, 13 VL repeats and 13 v5 repeats. A reserved attempt slot, a retained response and an actual model execution are different counts.

## References and scoring

References were authored and separately reviewed from the frozen images before development outcomes. Both reviewers were agents with disclosed shared context. These are reviewed development labels, not human ground truth.

All 33 pages have a reference disposition: 26 have partial transcription and seven are not transcribed. The labels contain 104 selected amount occurrences and 12 selected rows or captions. No page has a complete transcription suitable for whole-page omission measurement.

Amount scoring associates image geometry before comparing text. Only mutually unique, supported associations qualify. The paired denominator uses the same page and reference amount ID in both models, separately for each pass. Exact literal matching evaluates digits and decimal placement jointly; printed signs are also compared. Headings and reconciliation are not used to infer signs or financial validity.

Unsupported grammar, multi-amount regions, markup, unmatched anchors and ambiguous geometry remain separate from measured errors. The frozen grammar does not normalize French decimal commas or reconstruct split literals. Word-object counts from v5 and region-object counts from VL are different denominators.

### Development request outcomes

Values below are **documents/pages**. “Accepted” means that the extraction evidence passed this experiment’s adapter/frame contract; it does not mean a validated statement.

| Model | Pass | Modality | Requested | Attempted | Received | Accepted | Refused | Gated | Unattempted eligible |
|---|---|---|---|---|---|---|---|---|---|
| v5 | first | digital | 2/7 | 1/5 | 1/5 | 1/5 | 0/0 | 1/2 | 0/0 |
| vl | first | digital | 4/16 | 3/14 | 3/14 | 3/14 | 0/0 | 1/2 | 0/0 |
| v5 | first | scanned | 2/8 | 2/8 | 2/8 | 2/7 | 1/1 | 0/0 | 0/0 |
| vl | first | scanned | 4/13 | 4/13 | 4/13 | 3/9 | 2/4 | 0/0 | 0/0 |
| v5 | first | mixed | 2/2 | 0/0 | 0/0 | 0/0 | 0/0 | 2/2 | 0/0 |
| vl | first | mixed | 4/4 | 0/0 | 0/0 | 0/0 | 0/0 | 4/4 | 0/0 |
| v5 | second | digital | 2/7 | 1/5 | 1/5 | 1/5 | 0/0 | 1/2 | 0/0 |
| vl | second | digital | 2/7 | 1/5 | 1/4 | 1/4 | 1/1 | 1/2 | 0/0 |
| v5 | second | scanned | 2/8 | 2/8 | 2/8 | 2/7 | 1/1 | 0/0 | 0/0 |
| vl | second | scanned | 2/8 | 2/8 | 2/8 | 2/8 | 0/0 | 0/0 | 0/0 |
| v5 | second | mixed | 2/2 | 0/0 | 0/0 | 0/0 | 0/0 | 2/2 | 0/0 |
| vl | second | mixed | 2/2 | 0/0 | 0/0 | 0/0 | 0/0 | 2/2 | 0/0 |

Across both models and passes: 84 requested page slots, 18 gated, 66 attempted, 65 responses, 59 accepted observations and seven refusals. Six refusals retained responses; one transport refusal did not. There were no automatic retries or remaining eligible slots.

Document state counts mean documents with at least one page in the named state. A document can contain both admitted and refused pages, so those document counts overlap. Repeats do not increase the unique document sample.

### Paired amount and sign results

| Pass | Modality | Both accepted D/P | Common-label D/P | Common amounts | v5 exact literal | VL exact literal | v5 exact sign | VL exact sign |
|---|---|---|---|---|---|---|---|---|
| first | digital | 1/5 | 0/0 | 0 | unmeasured | unmeasured | unmeasured | unmeasured |
| first | scanned | 2/7 | 1/1 | 1 | 0 | 1 | 1 | 1 |
| first | mixed | 0/0 | 0/0 | 0 | unmeasured | unmeasured | unmeasured | unmeasured |
| second | digital | 1/4 | 0/0 | 0 | unmeasured | unmeasured | unmeasured | unmeasured |
| second | scanned | 2/7 | 1/1 | 1 | 0 | 1 | 1 | 1 |
| second | mixed | 0/0 | 0/0 | 0 | unmeasured | unmeasured | unmeasured | unmeasured |

The same single scanned-page amount is the common denominator in both passes. VL recovered its printed literal exactly; v5 did not. Both preserved its printed sign. This is one repeated finding, not two independent examples. There are no measured v5-only wins on the common set, and no measurable digital or mixed amount comparison. The sample cannot establish a general accuracy improvement or regression rate.

The following are model-specific association counts on accepted pages. They explain measurement coverage; different denominators and extra unpaired VL pages make them unsuitable as a model accuracy comparison. “Literal/sign unsupported” describes the frozen scoring grammar or label status, not an OCR error.

| Model | Pass | Modality | Reviewed amounts | Eligible reference amounts | Associated | Exact literal | Exact sign | Literal/sign unsupported | Ambiguous geometry | Other unmatched/unsupported |
|---|---|---|---|---|---|---|---|---|---|---|
| v5 | first | digital | 20 | 0 | 0 | 0 | 0 | 20 | 0 | 0 |
| vl | first | digital | 56 | 32 | 4 | 4 | 4 | 24 | 27 | 1 |
| v5 | first | scanned | 28 | 12 | 11 | 2 | 11 | 16 | 0 | 1 |
| vl | first | scanned | 32 | 16 | 1 | 1 | 1 | 16 | 12 | 3 |
| v5 | second | digital | 20 | 0 | 0 | 0 | 0 | 20 | 0 | 0 |
| vl | second | digital | 16 | 0 | 0 | 0 | 0 | 16 | 0 | 0 |
| v5 | second | scanned | 28 | 12 | 11 | 2 | 11 | 16 | 0 | 1 |
| vl | second | scanned | 28 | 12 | 1 | 1 | 1 | 16 | 8 | 3 |

On paired scanned pages, v5 has ten additional supported associations per pass outside the common set. VL’s four additional first-pass digital associations are from pages without fresh paired v5 results. No value comparison is inferred from either group.

Reference rows/captions do not supply complete transaction inventories. Whole-page token omissions, additions and transaction-row completeness remain unmeasured for every eligible document/page. Candidate exclusions include markup, multi-amount regions, unknown generation termination and unsupported lexemes. Counts of v5 words and VL regions must not be compared as coverage percentages.

| Model / pass | Financial reconstruction and whole-page completeness unmeasured D/P | Word geometry unsupported among accepted D/P | Refused evidence unavailable D/P |
|---|---:|---:|---:|
| v5 first | 3/13 | 0/0 | 1/1 |
| v5 repeat | 3/13 | 0/0 | 1/1 |
| VL first | 7/27 | 6/23 | 2/4 |
| VL repeat | 3/13 | 3/12 | 1/1 |

Refused, unsupported and unmeasured categories address different questions and overlap. Gated non-statements are shown separately in the request table.

### Repeat stability

| Model | Modality | Scheduled page pairs | Measured | Equal | Different | Unmeasured/gated |
|---|---|---|---|---|---|---|
| v5 | digital | 7 | 5 | 5 | 0 | 2 |
| v5 | scanned | 8 | 7 | 7 | 0 | 1 |
| v5 | mixed | 2 | 0 | 0 | 0 | 2 |
| vl | digital | 7 | 4 | 4 | 0 | 3 |
| vl | scanned | 8 | 8 | 8 | 0 | 0 |
| vl | mixed | 2 | 0 | 0 | 0 | 2 |

Each model has 12 equal measurable pairs, covering three documents, with no observed difference under its own equality definition. The measurable cohorts differ: v5 has five digital and seven scanned pages; VL has four digital and eight scanned pages. All 12 retained response-file pairs per model differed in bytes. The other five scheduled pairs per model are unmeasured or gated.

The v5 repeat comparison uses full canonical page-record equality. The VL repeat comparison uses its predefined stable evidence projection. These are distinct equality definitions. Byte equality also has different serialization scopes: v5 retains parsed-response files, while VL retains HTTP response bodies.

## Synthetic capability check

All 32 scheduled fixture requests completed: 16 per model, including eight fixed repeat pairs. There were no extra warmups or retries outside that schedule. Both models reproduced their predefined stable evidence on all eight synthetic repeat pairs. All retained response-file pairs differed in bytes.

| Ordered fixture measure, per eight-fixture pass | v5 | VL |
|---|---:|---:|
| Matched whitespace tokens, of 366 reference tokens | 235 | 349 |
| Substitutions | 125 | 12 |
| Omissions | 6 | 5 |
| Additions | 21 | 5 |
| Ordered amount-role recovery, of 81 | 40 | 77 |
| Ordered CR/DR-role recovery, of 53 | 25 | 49 |

Reading-order differences confound these ordered comparisons. Three fixtures have identical token multisets across models. These figures describe the invented fixtures; they are not isolated digit-error rates, transaction accuracy or customer-statement accuracy.

The frame and output checks established region geometry for VL. Word geometry remains unsupported. Seventy observed synthetic generations terminated before the cap; that does not prove full-page recall.

## Geometry, completeness and downstream limits

The experiment preserves actual source-image bindings and model geometry. It does not fabricate word boxes or repair out-of-frame coordinates. The first v5 pass refused one page with four nonblank word boxes outside its raster. VL refused four pages with out-of-frame polygons. A separate interrupted VL slot retained no response and was not replayed.

Across 35 admitted VL page observations, 367 region generations were recorded. Of these, 365 had an observed terminator before the cap and two were unknown or capped. Both uncertain observations occurred on the same page, once in each pass. This denominator covers generations on admitted pages, not all requested pages or whole-page recall.

| Required measurement | Evidence available |
|---|---|
| Printed amounts and signs | Conditional paired measurements above; limited to reviewed supported associations |
| Decimal placement | Included in exact literal matching; no separate decimal-only error attribution |
| Debit/credit fidelity | Printed signs and synthetic CR/DR roles; heading-derived financial effects unmeasured |
| Missing or extra page tokens | Ordered synthetic counts only; development pages lack complete references |
| Transaction rows and page completeness | Unmeasured; partial references cannot establish recall or additions |
| Geometry and traceability | v5 word evidence and VL region evidence retained; unsupported geometry and refusals explicit |
| Common downstream reconstruction and validation | Unsupported with VL's current region-only contract and the existing word consumer |
| False accepts | Unmeasured; reconciliation was not used as ground truth |

## Runtime and resources

Both models used the same frozen 300 dpi Poppler CropBox PNGs on the configured GPU instance. Calls were serial. Lossless SSH compression preserved the raster bytes.

| Pass | Included pages | Median ms | Observed range ms | Measured scope |
|---|---|---|---|---|
| v5-first | 11 | 473.62 | 326.56–529.43 | worker inference |
| v5-second | 11 | 487.48 | 345.91–543.24 | worker inference |
| vl-first | 22 | 10,273.77 | 2,152.78–45,771.20 | pipeline plus observer |
| vl-second | 11 | 12,157.70 | 5,283.61–45,328.43 | pipeline plus observer |

These are descriptive timings on accepted observations, not matched model benchmarks. The first-pass VL cohort is larger. After the timing exclusions, 11 v5 repeat pairs and ten VL repeat pairs have both timings available. All of those pairs cross campaign sessions. Transfer-only timings and a comparable v5 remote-memory peak remain unmeasured.

The recorded scopes differ: v5 reports worker inference, while VL reports pipeline time including the generation observer. Client durations and total windows include additional work. Transfer time was not isolated, so subtracting the two would not establish pure upload time. First-worker calls were excluded according to the frozen timing rules. Restarts introduced additional exclusions and cross-session comparisons. These observations do not establish a controlled cold-model or kernel-speed ranking.

The three VL windows recorded sampled peak GPU usage of 19,188,940,800; 19,480,444,928; and 17,016,291,328 bytes, using 502, 276 and 303 samples respectively. Sampled process RSS peaks were 3,048,259,584; 3,076,382,720; and 3,050,536,960 bytes. These are observed sampled peaks, not kernel-enforced reservations. Comparable v5 remote GPU-memory measurements are unavailable.

The earlier 33-hour estimate concerned a full population run. It is not the duration or a measured baseline for this bounded study.

## Configuration and bindings

| Setting | PP-OCRv5 | PaddleOCR-VL-1.6 |
|---|---|---|
| Models | PP-OCRv5_server_det and en_PP-OCRv5_mobile_rec | PP-DocLayoutV3 and PaddleOCR-VL-1.6-0.9B |
| Runtime | Python 3.12.3, PaddleOCR 3.7.0, PaddlePaddle 3.3.0, PaddleX 3.7.2 | Same versions; NumPy 2.3.5 and Pillow 12.1.0 |
| Engine / precision | Verified paddle_static; precision unrecorded | Native paddle generation; VL bfloat16; layout precision unrecorded |
| Preprocessing | Document orientation, unwarping and text-line orientation off; recognition threshold 0.0 | Document orientation and unwarping off; layout detection on |
| Concurrency | One worker, serial pages | GPU 0, batch size 1, queues off, layout CPU workers 0 |
| Decoding | Existing production settings | Greedy, one beam and sequence, cache on, maximum 4,096 new tokens per region |
| Recognition image bounds | Existing production settings | 112,896–1,003,520 pixels |
| Hardware | RTX 5090, driver 580.105.08 | Same observed GPU and driver |

The VL model revision is c5630abae1d940eafe0697512a0325494b02ab42; the layout revision is 7b48a7566925fa464281f930c58eee04fe2c862a. Fifteen model-asset files totaling 2,062,282,301 bytes were verified. The isolated dependency overlay contained 26 distributions and left all 87 original base metadata records unchanged.

Exact v5 asset inventories, installed sources, runtime recipes and image/reference/response bindings are retained privately. A v5 official model revision and precision were not recorded and are not inferred. The retained [VL documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/docs/version3.x/pipeline_usage/PaddleOCR-VL.en.md) and installed-source checks establish the route used here; public benchmarks are not bank-statement accuracy measurements.

The private partition retains the original and repeat outputs, refused outcomes, per-request raster bindings, generation observations, source inventories and failed-run records. Key frozen metadata bindings are:

| Artifact | SHA-256 |
|---|---|
| Selected development membership | 1bf842839ecf69ffc3027e2727d97a6667c83b40d87aefbfc66bb2ca5f37da18 |
| 84-slot request schedule | d053db428294112ea80f69cb97ea36ac270fa07241cbe46b2e832fc5981705b5 |
| Raster packet manifest | 17a4ed0fef56cb0c57a7b560d20a5a7cea5b5e433973c0bc2a67b4cc68fb7faa |
| Statement-kind gate | 927fd2ce8da3f9213afdd6205ada7db6cdb91eff62080750a2e32a2a8cc86e59 |
| Reviewed reference manifest | d786b0739972eda355631310cc835757afe534cc9335ce41b3a22b55df730543 |
| Retained native runtime recipe and observed wire identifier | 90876e1b035c1c9835baa72f86d53bf58ea1cddc1368a8dbca074482c6732da5 |
| Synthetic scoring report | 1b762eebb01e4c776a7cbfa463da03379114ff2ca56269258e8318694d1bfc86 |

The runtime recipe hash above identifies the exact retained file and observed wire identifier. It is distinct from a reserialized canonical-JSON hash.

| Final artifact | SHA-256 |
|---|---|
| Exact scoring authority | 7512f445d3406b2b2def51bd26578f9e25a31712b54fa6b773e7afbbb641f493 |
| Development scoring report | d0ab5fef3b44e8b400603531bcbce4a705729fe909b38b8aeebe7393d85fcf26 |
| Development aggregate report | 59244f00a6601037cf5da764468d2e1ee4d93ba8bb38087020a844b205a942ff |
| Scoring completion record | 26dd1015bdfa1e743b04f07e500a1156efa2dea82f24e2139bcd9a692e74b042 |

Offline scoring verified all 162 bound files unchanged and closed with zero read-boundary denials, zero image/original-document reads and zero new model calls. Existing 14 amount-association, 11 candidate-projection and 16 native-join checks were reused. The scoring source preserves the frozen measurement and aggregation functions; later revisions handle retained failed-run records only.

## Provenance limitations

Original failed runs were retained. The first v5 pass lacks final audit counters. Both VL continuation wrappers recorded one unexplained blocked input access; their guards did not retain the original event or path. Independent offline checks verified current retained files, sources and worker-exit evidence without repeating OCR. They do not retrospectively establish zero audit denials or unchanged historical file identity.

The scorer checks admitted native stable content against hashes in the original campaign records, in addition to current byte bindings. An interrupted monitor SSH stream and its separately fetched resource record remain distinct evidence. Failed slots are not silently converted into successful runs.

The final v5 repeat also returned 13 responses and admitted 12 pages. The remaining page was refused by the adapter; its precise adapter failure subtype was not diagnosed. The source/input audit completed unchanged with zero denials. Its main cleanup flag remained false despite a passing remote worker-absence attestation. Source review narrows that discrepancy to the subsequent local port check or an exception in that check; the original record does not distinguish them. A separate emergency check verified that the tunnel was absent and the remote worker and temporary files were gone. The main attestation records retention_declared=true and passed=true. The emergency attestation records retention_declared=false and passed=false; its separate physical-absence checks passed. Both the failed main status and the separate cleanup result are retained.

No document, filename, page count, hash or content from the reserved unseen batch was accessed for this comparison.


## Consequences for the remaining plan

Phase 2.4/2.5 should preserve the distinction between word evidence and region/table evidence. A future VL integration would need a separately reviewed way to consume its actual geometry, preserve printed-value provenance, handle refusal/completeness limits and pass the same deterministic validator. This study supplies no basis for a parser-specific workaround or validator-driven OCR selection.

A further research proposal should freeze a measurement contract that can evaluate printed amounts represented inside regions or tables and supported decimal formats, then evaluate fresh development evidence with complete independent labels. It must preserve this study’s results and keep the reserved unseen batch out of tuning. No expanded experiment is authorized by this report.

The later Unlimited OCR go/no-go assessment should use these unresolved evidence-contract and completeness gaps as comparison requirements. Neither the synthetic scores nor a single development amount justifies skipping that assessment. Existing Phase 2.3 configuration comparisons and V/B/P composition debts remain separate and must close before phase advancement.

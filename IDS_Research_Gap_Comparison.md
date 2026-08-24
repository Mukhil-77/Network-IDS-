# IDS Research-Gap Comparison: Research PDF vs. Actual Network-IDS Project

## 1. Purpose and source-integrity note

This report compares the **actual implementation in `Network-IDS--main.zip`** against the research literature contained in `Recent_research.pdf`.

A critical source-integrity point: the uploaded PDF is a **multi-paper compilation**, not a single standalone article. For the main comparison, the reference paper is treated as the first major article in the PDF:

> **Vadym Poltoratskyi and Svitlana Gavrylenko, “The Evolution of Intrusion Detection Systems: A Comprehensive Review of Modern Datasets, Deep Learning Approaches, and Architectural Challenges,” Advanced Information Systems, 2026.**

The later 2026 material in the same PDF is used only as corroborating recent research, especially where it gives stronger validation and deployment guidance. This avoids pretending that recommendations from a separate paper were made by the primary review.

The code-side conclusions below were derived from the source tree and the trained artifacts in the ZIP, not from the README alone.

---

# 2. Executive conclusion

The current project is much more than a notebook classifier. The codebase already contains a **live packet-capture pipeline, flow reconstruction, ML inference, alert persistence, WebSocket alerting, severity mapping, threat-intelligence enrichment, an automated response engine, response history, rollback support, model versioning, Prometheus/Grafana deployment support, and an Electron desktop application**.

That gives the project a strong engineering base.

However, the current implementation has four research weaknesses that are more important than adding another classifier:

1. **The training/evaluation pipeline has a data-leakage problem in the multiclass path:** SMOTE is applied before the train/test split, so the reported performance is not a clean leakage-free estimate.
2. **Rare attacks are deliberately removed before multiclass training:** classes with `<= 1950` examples are dropped, which weakens the project's claim of rare-attack and zero-day readiness.
3. **The deployed detector is not truly uncertainty-aware:** the current confidence is simply the maximum classifier probability, while live feature coverage can be incomplete and missing features are replaced by `0.0`; the coverage information is logged but is not incorporated into the stored alert's confidence/risk.
4. **The platform contains automated response infrastructure, but not yet verified self-healing:** several actions are simulation-only or placeholder implementations, and `increase_monitoring` records intent rather than changing a running detector.

The strongest research contribution is therefore **not** “use a more advanced deep-learning model.” The project can stand out by turning the existing system into a **deployment-aware, leakage-free, confidence-aware, generalization-tested, explainable, closed-loop IDS** while keeping the current architecture.

---

# 3. What the reference research paper does

## 3.1 Approach used by the primary paper

The primary paper is a **systematic review of IDS research from 2020–2025**, organized around a broad taxonomy. It examines:

- detection strategy: signature-based, anomaly-based, hybrid;
- deployment: HIDS, NIDS, distributed/edge/fog;
- data source: packets, flows, logs, and multi-source data;
- response/autonomy: passive IDS, active IPS, SOAR-like automation;
- architecture: centralized versus decentralized/federated;
- datasets and validation strategies;
- traditional ML, deep learning, Transformers, graph models, federated learning, XAI, and other emerging approaches.

The review explicitly argues that benchmark accuracy is no longer sufficient. It identifies class imbalance, unknown/zero-day attacks, real-world scalability, privacy, model generalization, interpretability, and deployment as unresolved issues. The abstract specifically notes that many benchmark systems exceed 98% accuracy while those problems remain open. fileciteturn0file0L9-L29

## 3.2 What the paper does well

### A. It correctly moves the evaluation discussion beyond accuracy

The paper emphasizes that high accuracy on benchmark data does not automatically imply operational usefulness. It discusses false positives, false negatives/rare-attack misses, adversarial robustness, class imbalance, generalization, computational requirements, and real-world deployment.

### B. It recognizes the dataset problem as a first-class research issue

The paper explains that older benchmark datasets are unrealistic or outdated and that newer datasets still have imbalance, incomplete zero-day representation, and limited dynamic behavior. It also notes that there is no single universal dataset that solves all IDS evaluation requirements.

### C. It connects detection to deployment

The taxonomy does not stop at a classifier. It considers NIDS deployment, distributed/edge processing, response mechanisms, and the shift from passive IDS toward IPS/SOAR-style autonomous response. The paper explicitly describes systems that can isolate threats dynamically in real time. fileciteturn1file1L117-L149

### D. It gives XAI a practical security purpose

The paper does not treat explainability as a cosmetic visualization. It ties XAI to analyst trust and the ability to understand why a flow was classified as malicious. SHAP/LIME are explicitly proposed as directions for complex IDS models. fileciteturn5file0L98-L130

### E. It identifies better validation protocols

The 2026 material in the same PDF recommends cross-dataset validation, time-aware splits, device-level testing, Macro-F1/per-class F1, FPR, PR-AUC, and resource metrics instead of relying on a random holdout and accuracy alone. fileciteturn5file1L346-L384

---

# 4. Main research limitations identified in the PDF

The limitations most relevant to this project are:

| Research limitation | What the literature says |
|---|---|
| False positives / alert fatigue | Anomaly-oriented systems can generate high FPR, reducing operator trust and producing alert fatigue. |
| False negatives / rare attacks | Severe imbalance can make minority attacks poorly detected even when global accuracy is high. |
| CIC-IDS2017 / benchmark dependence | Benchmark datasets can produce optimistic results and do not fully represent current networks, dynamic traffic, adversarial behavior, or encrypted traffic. |
| Class imbalance | Majority traffic dominates training, so minority attacks can be ignored or underlearned. |
| Unseen / zero-day attacks | Models trained on historical attack classes may not generalize to new threat vectors. |
| Cross-dataset generalization | A model that performs well on one dataset can degrade when traffic distributions and attack taxonomies change. |
| Real-time deployment | Accuracy alone does not establish latency, throughput, resource consumption, or deployment feasibility. |
| Explainability | High-performing ML/DL systems often do not explain why a prediction was made. |
| Confidence / reliability | Operators need to know not just the predicted class but how reliable that decision is. |
| Concept drift | Changing traffic patterns and topology can make a static model stale. |
| Adversarial robustness | IDS models can be manipulated through crafted inputs or poisoned training data. |
| Automated response | The research direction is moving toward adaptive response, but safe autonomous actions require reliability, auditability, and rollback. |
| Full attack lifecycle | Many systems classify isolated flows instead of understanding multi-stage behavior. |
| Real-world/SOC integration | Controlled experiments do not prove that an IDS can reduce analyst workload or integrate cleanly into operations. |

The primary paper is especially explicit about false positives, imbalance, zero-day/adversarial generalization, encrypted traffic, concept drift, and deployment gaps. fileciteturn5file0L22-L97

The paper further argues that benchmark performance above 98% can coexist with limited real-world applicability because of imbalance, adversarial vulnerability, heterogeneous data, and model opacity. fileciteturn5file0L157-L251

---

# 5. What the actual project currently implements

## 5.1 Core architecture already present

The ZIP contains a real SOC-oriented implementation rather than only a model notebook. The implemented path is approximately:

**packet capture → flow construction → feature extraction → live/model feature mapping → validation → scaling/PCA → classifier → confidence → severity → alert persistence → threat-intelligence enrichment → response policy → response execution → response history → dashboard/WebSocket**

The project also includes:

- FastAPI backend;
- React dashboard;
- Electron desktop packaging;
- PostgreSQL/SQLAlchemy models;
- WebSocket live alert streaming;
- Prometheus/Grafana deployment support;
- Docker deployment;
- model version directories (`v1`–`v4`);
- tests for ML, inference, severity, confidence, validation, and response components.

The README confirms the platform is intended for real-time threat detection and automated incident response, and lists packet capture, ML classification, WebSocket alerts, response automation, analytics, monitoring, Docker, and the Windows desktop application. **These capabilities are also backed by actual modules in the ZIP.**

## 5.2 Current ML model

The deployed artifacts are trained on **CIC-IDS2017** and use a StandardScaler + IncrementalPCA pipeline. The versioned artifacts use 35 PCA components.

The trained artifacts actually expose these six output classes:

- BENIGN
- Bot
- Brute Force
- DDoS
- DoS
- Port Scan

That is important: although the label-mapping code knows about additional labels such as Web Attack, Infiltration, Heartbleed and UNKNOWN, the current versioned classifiers loaded from `models/v1`–`models/v4` expose only the six classes above.

The best stored artifact (`v2`) reports:

- accuracy: **98.56%**
- precision: **98.56%**
- recall: **98.55%**
- F1: **98.55%**

These values are stored in `models/v2/metadata.json`.

**Important methodological qualification:** these numbers must not be presented as a leakage-free research benchmark because the multiclass training pipeline applies SMOTE before the train/test split. That issue is explained in Section 6.

---

# 6. The most important code-level finding: current multiclass evaluation leaks information

This is the first issue that should be fixed before claiming a new research contribution.

In `backend/ml/training.py`, the multiclass pipeline does the following:

1. removes classes with `<= 1950` examples;
2. caps some large classes;
3. applies `SMOTE.fit_resample()` to the complete selected dataset;
4. then creates the train/test split.

The relevant source is `backend/ml/training.py`, approximately lines 208–245.

That order matters. Synthetic samples are generated before the held-out test set exists. Therefore synthetic points derived from examples can end up on both sides of the later split. This makes the test set less independent from the training data than it should be.

This is not a minor implementation detail. It means the current 98.56% result should be treated as **an existing baseline result, not as a final clean estimate of generalization**.

### Why this is a research opportunity

Instead of hiding the problem, turn it into a contribution:

> **Leakage-free imbalance-aware IDS evaluation for operationally relevant minority attacks.**

The corrected experimental protocol should split first and apply oversampling only inside the training data/process. The test set must preserve the original distribution.

Then compare:

- existing pipeline;
- leakage-free baseline;
- leakage-free + class weighting;
- leakage-free + targeted minority augmentation/resampling.

This produces a much stronger research story than “our model achieved 99% accuracy.”

---

# 7. Second major code-level finding: rare classes are removed before training

`prepare_multiclass_dataset()` keeps only classes whose count is greater than `1950`.

The source itself documents this behavior: classes with `<= 1950` examples are dropped entirely before balancing.

That is directly at odds with a major research challenge identified in the paper: rare threats are exactly where accuracy-centered evaluation is weakest.

This also explains why the actual trained models currently expose only six classes even though the dataset mapping logic contains more categories.

### Research implication

The project should not claim “zero-day readiness” merely because it has a multiclass model. A closed-set classifier cannot automatically recognize an attack class it was never trained to represent.

The improvement should be:

- retain rare attack families where the dataset supports them;
- do not use a minimum-count rule that silently removes difficult classes;
- evaluate minority recall and per-class F1;
- separately evaluate **unknown/novel traffic detection** rather than forcing every unknown input into one of the known six labels.

---

# 8. Direct limitation-to-project comparison

| Research paper limitation | What the project currently does | What is still missing | What to add/improve | How it addresses the limitation | Why it stands out |
|---|---|---|---|---|---|
| High false positives / alert fatigue | Classifies every completed flow and stores severity/confidence; dashboard shows confidence and severity | No learned alert threshold, no calibration, no alert-burden metric, no confidence-aware suppression/abstention | Calibrated probability + risk score + analyst/automatic threshold tiers | Reduces low-value alerts and measures operational false-alarm burden | Connects model output to SOC workload instead of only classification accuracy |
| False negatives / rare attacks | SMOTE is present | SMOTE is applied before split; rare classes are removed; minority recall is not the main optimization target | Leakage-free balancing + rare-class retention + cost-sensitive evaluation | Gives rare attacks an independent test and prevents majority-class dominance | Research claim is about rare-attack sensitivity, not global accuracy |
| CIC-IDS2017 dependence | Full training pipeline is built around CIC-IDS2017 | No external dataset validation or domain-shift analysis | Cross-dataset evaluation with feature harmonization | Shows whether learned patterns transfer beyond the benchmark | Turns a benchmark IDS into a generalization study |
| Zero-day / unseen attacks | `UNKNOWN` exists in label mapping but current trained classifiers do not output it as a learned unknown detector | No OOD/novelty detector or abstention | Unknown/OOD layer + confidence threshold + held-out attack-family experiment | Prevents forcing unseen traffic into a known class | Directly addresses one of the most important open IDS problems |
| Generalization / concept drift | Model versions can be loaded/switched; live monitoring exists | No temporal validation, drift detector, or automatic update gate | Time-aware tests + drift monitoring + validated model promotion | Demonstrates robustness to changing traffic | Connects research evaluation to continuous operations |
| XAI | No SHAP/LIME or explanation object in the detection path | Analyst does not see why an alert was produced | Local SHAP-style explanation for RF + PCA-aware feature attribution | Makes prediction evidence auditable | Explanations are attached to real alerts rather than a separate notebook demo |
| Confidence reliability | Uses `max(predict_proba)` as confidence | No calibration or uncertainty estimate | Probability calibration + ECE/Brier + abstention | Makes confidence more trustworthy | Adds deployment reliability to an existing confidence field |
| Live feature mismatch | Live feature mapper records coverage and fills unavailable features with 0.0 | Coverage is logged but not integrated into prediction confidence/risk/alerting | Coverage-aware confidence/risk penalty | Prevents overconfidence when live telemetry is incomplete | Specifically addresses the difference between offline features and deployed features |
| Severity | Fixed label→severity map exists and is configurable | Severity is mostly attack-class based; it is not contextual | Context-aware risk score using severity + calibrated confidence + asset/context + repetition + TI | Better prioritizes analyst attention and automation | Creates a bridge between ML confidence and SOC decision-making |
| Automated response | Automatic response workflow exists and records results | Several actions are simulation-only or placeholders; default policy is simulation mode | Confidence-gated, reversible, verified response playbooks | Reduces unsafe automation and proves containment success | Moves from “automated response exists” to “response is measurable and trustworthy” |
| Self-healing / recovery | Rollback infrastructure exists; some recovery actions exist | No verified closed-loop recovery; `increase_monitoring` only records intent | Post-response verification + rollback + recovery-state verification | Demonstrates whether the action actually reduced malicious activity | Gives the project an end-to-end detection→response→verification loop |
| Adversarial robustness | No adversarial training/evaluation found in the current pipeline | Unknown behavior under crafted/evasive traffic | Controlled robustness/evasion test set before model promotion | Measures degradation under manipulation | Makes robustness a measurable system property |
| Real-world deployment | Live capture, async inference, Docker, monitoring, Electron | No complete end-to-end performance contract linking traffic rate, prediction latency, response latency and resource use | Throughput/latency/resource benchmark under sustained capture | Proves practical deployment instead of asserting it | Stronger than benchmark-only evaluations |

---

# 9. Detailed improvement analysis by requested research area

## 9.1 False positives and false negatives

### Current project

The project already exposes a `confidence` value and `severity` value in the alert model and dashboard. It also computes confusion matrices and macro precision/recall/F1 during offline evaluation.

### Problem

The current confidence is only:

> maximum predicted probability from `predict_proba()`.

It is not calibrated confidence. A model can report 99% probability without that 99% corresponding to a 99% empirical correctness rate.

Also, the current evaluation emphasizes accuracy, macro precision, macro recall and macro F1, with ROC/PR curves for binary models. It does not make **MCC, FPR, false alerts per time period, or analyst alert burden** first-class results.

### Improvement

Create an evaluation and runtime policy around:

- FPR;
- FNR / missed attack rate;
- per-class recall;
- Macro-F1;
- MCC;
- PR-AUC for rare attacks;
- alerts per 1,000 flows;
- false alerts per hour;
- calibrated confidence;
- abstention/analyst-review rate.

Then choose thresholds according to operational cost, not the maximum possible accuracy.

### Research contribution

The novelty is not another algorithm. It is **cost-aware and confidence-aware operation of the existing IDS**.

---

## 9.2 CIC-IDS2017 limitation

### Current project

The complete training pipeline and current model artifacts are built around CIC-IDS2017. The project uses 70 raw features that are standardized and reduced to 35 PCA components for the deployed models.

### Problem

The research literature in the PDF repeatedly warns that single benchmark datasets can produce overly optimistic claims. Cross-dataset work in the PDF recommends training on one corpus and testing on another, because traffic distributions and attack characteristics change. fileciteturn5file1L391-L417

### Improvement

Keep the current model architecture. Do **not** redesign the whole project.

Instead add a validation track:

**CIC-IDS2017 → harmonized feature subset → external dataset test**

Candidate external validation sets from the literature in the PDF include UNSW-NB15, TON-IoT, Edge-IIoTset and CICIoT2023.

The key experiment is not “train on everything.” It is:

> train on CIC-IDS2017, freeze the model, then test on a different dataset without retraining.

A second experiment can train on the external dataset and test on CIC-IDS2017 to quantify asymmetry in transfer.

### Why it stands out

A large number of IDS papers show excellent within-dataset performance. A project that reports **how much performance survives dataset shift** is more scientifically defensible.

---

## 9.3 Class imbalance

### Current project

The code explicitly uses balancing and SMOTE.

### Problem

The implementation currently removes rare classes and applies SMOTE before train/test separation. That makes the system look balanced during evaluation without proving that the original rare-attack problem was solved.

### Improvement

Make the experiment explicitly separate:

1. original distribution;
2. leakage-free train-only balancing;
3. class-weighted baseline;
4. targeted rare-class augmentation;
5. untouched imbalanced test set.

Measure minority recall and false-negative rate, not only overall F1.

### Strong research framing

> “We evaluate minority-attack detection under the original imbalanced distribution and prevent resampling leakage by confining balancing to the training partition.”

That sentence is substantially stronger than simply saying “SMOTE was used.”

---

## 9.4 Unseen / zero-day attacks

### Current project

The source code maps unmatched raw labels to `UNKNOWN`, and the severity map contains an `UNKNOWN` category. However, the actual trained classifiers in `v1`–`v4` expose only six known classes. Therefore `UNKNOWN` is not currently a learned zero-day detector.

### Improvement

Add a separate novelty decision on top of the current classifier:

**Known-class prediction + novelty/OOD gate → known attack / suspicious unknown / benign**

The OOD gate can use a calibrated confidence/uncertainty score and should have an explicit “abstain” state.

A strong experimental design is **leave-one-attack-family-out**:

- remove one attack family from training;
- expose it only during testing;
- measure how often the model rejects it as unknown rather than incorrectly labeling it as a known class.

### Why this is stronger than claiming zero-day detection

Zero-day claims require an explicit unseen-threat experiment. A random train/test split cannot prove zero-day capability.

The PDF specifically recommends transfer/domain adaptation and active learning for unknown threats and heterogeneous distributions. fileciteturn5file0L136-L156

---

## 9.5 Explainable AI

### Current project

No SHAP/LIME-based explanation was found in the actual prediction path. Alerts contain:

- attack type;
- confidence;
- severity;
- source/destination;
- protocol;
- model version;
- processing latency.

### Improvement

For the existing Random Forest model, generate a local explanation for each important alert:

- top contributing features;
- contribution direction;
- confidence;
- model version;
- feature-coverage caveat.

A particularly good extension is **PCA-aware explanation**. Because the deployed model predicts from PCA components, the UI should not stop at “PC7 caused the alert.” The system should map the explanation back toward the original flow features so the analyst sees interpretable evidence such as packet length, IAT, flags, or byte/packet-rate features.

### Why this stands out

The PDF already says XAI should become more systematic. The differentiator is to make XAI **part of the operational alert record and response decision**, not a separate academic plot. fileciteturn5file0L107-L130

---

## 9.6 Detection confidence, risk scoring and alert prioritization

### Current project

The alert already has a confidence field and a fixed severity level. The dashboard also shows severity and confidence.

### Missing piece

The current confidence is not calibrated, and the current severity is essentially a static mapping from predicted attack class.

The live feature mapper is more interesting: it computes a feature coverage ratio and reports which required features were filled with `0.0`. However, the detection service does not propagate that report into the alert object. The alert therefore has no warning such as:

> “This confidence is based on only 72% of model features being reconstructed from live traffic.”

### Improvement

Create a **contextual risk score** from existing signals:

- calibrated model confidence;
- attack severity;
- feature-coverage ratio;
- threat-intelligence tag;
- repetition/frequency of the source;
- target/asset importance;
- response history for the same source;
- novelty/uncertainty.

Then sort the SOC queue by risk rather than raw timestamp.

### Research value

This directly addresses the literature's concern that analysts need to know the reliability of a prediction and that high FPR causes alert fatigue. The later 2026 review in the PDF explicitly recommends moving beyond accuracy to false-alarm burden, robustness, adaptability, inference time and deployment feasibility. fileciteturn5file2L482-L500

---

## 9.7 Real-time detection

### Current project

The system captures traffic live and uses a thread pool so inference does not block the flow-management thread. It stores processing latency and packet/flow statistics.

### Missing piece

There is not yet a complete research-grade operational benchmark that relates:

- packets/second;
- flows/second;
- detection latency;
- end-to-end alert latency;
- response latency;
- CPU;
- RAM;
- sustained-load behavior.

### Improvement

Run a sustained traffic test and report a small deployment profile:

> throughput → mean/median/p95 inference latency → p95 detection-to-alert latency → response latency → CPU/RAM → dropped flows.

That is enough to make the real-time claim experimentally defensible without changing the architecture.

The 2026 validation framework inside the PDF specifically recommends inference latency, memory footprint, CPU/energy overhead and other resource metrics alongside detection metrics. fileciteturn5file1L375-L384

---

## 9.8 Automated response

### Current project

The response engine is one of the strongest existing parts of the project. It:

- selects actions from a severity policy;
- supports automatic execution;
- records response history;
- updates alert status;
- emits WebSocket response events;
- supports rollback for rollback-capable actions.

### Missing piece

The default response policy is `simulation_mode: true`. Several actions are explicitly simulated. `quarantine_host` has no real VLAN/switch-port implementation, `restart_service` uses a placeholder target service, `kill_process` does not target an actual malicious process, and `increase_monitoring` records intent rather than changing a live capture process.

### Improvement

Do not rewrite the response engine. Turn it into a **verified response loop**:

1. calculate calibrated risk;
2. choose a bounded response playbook;
3. execute the response;
4. verify that the threat indicator actually decreases;
5. mark containment successful or failed;
6. rollback when a false positive is detected;
7. record the before/after evidence.

### Experimental proof

Measure:

- detection-to-response latency;
- percentage of successful response actions;
- percentage of false blocks;
- containment time;
- rollback success rate;
- attack traffic reduction after response;
- recovery time.

This creates a measurable **detect → decide → act → verify → recover** contribution.

---

# 10. The 4 strongest improvements to make the project a genuine research contribution

## Contribution 1 — Leakage-free, rare-attack-aware IDS evaluation

### Problem in existing research

Benchmark studies can report very high accuracy while class imbalance, rare attacks and evaluation methodology hide weaknesses. The PDF states that accuracy above 98% can coexist with unresolved class imbalance and real-world reliability problems. fileciteturn0file0L23-L29

### Why it is a disadvantage

A model can look excellent because the test data is statistically close to the training data, because majority classes dominate, or because resampling has leaked information into the evaluation set.

### What our current project already has

- CIC-IDS2017 preprocessing;
- class balancing;
- SMOTE;
- Random Forest/KNN variants;
- confusion matrices;
- macro precision/recall/F1;
- versioned model artifacts.

### What we should improve

- split before SMOTE;
- preserve the original test distribution;
- stop dropping rare classes simply because they are small;
- add MCC, FPR, FNR, PR-AUC and per-class recall;
- report the minority classes separately.

### How the improvement addresses the disadvantage

It makes the experiment statistically cleaner and makes rare-attack performance visible instead of hiding it behind a single global accuracy figure.

### Why this makes the project stand out

The project can claim **evaluation integrity** as a contribution rather than merely another high-accuracy CIC-IDS2017 result.

### How we can experimentally prove it

Run the same model under:

- current pipeline;
- leakage-free baseline;
- leakage-free + class weighting;
- leakage-free + targeted minority strategy.

Compare macro-F1, MCC, FPR, FNR, PR-AUC and minority-class recall on an untouched test set.

---

## Contribution 2 — Cross-dataset and explicit unseen-attack generalization

### Problem in existing research

Single-dataset evaluation does not establish generalization. The 2026 literature in the PDF explicitly recommends cross-dataset and time-aware validation because traffic and attack distributions differ between datasets and environments. fileciteturn5file1L346-L417

### Why it is a disadvantage

A CIC-IDS2017-trained model can learn the statistical fingerprint of the benchmark rather than general attack behavior.

### What our current project already has

- a stable model artifact format;
- feature validation;
- versioned models;
- a live inference API;
- a feature-mapping layer that can be extended to a common feature subset.

### What we should improve

Add a cross-dataset evaluation track and an explicit unknown/OOD decision:

- train on CIC-IDS2017;
- freeze the model;
- test on an external dataset after feature harmonization;
- use chronological splits where possible;
- run a leave-one-attack-family-out experiment;
- allow an “unknown/suspicious” state.

### How the improvement addresses the disadvantage

It directly tests whether the learned behavior survives traffic and attack distribution changes.

### Why this makes the project stand out

The project becomes a **generalization study and deployment system**, not only a benchmark classifier.

### How we can experimentally prove it

Report:

- in-dataset performance;
- cross-dataset performance;
- degradation percentage;
- unknown-detection TPR/FPR;
- confusion of unseen attacks into known classes;
- calibration on known vs. unseen traffic.

---

## Contribution 3 — Coverage-aware calibrated confidence → risk score → explainable alert prioritization

### Problem in existing research

Security analysts need to know not only what the model predicted but why and how reliable the prediction is. The PDF identifies explainability and deployment trust as persistent gaps. fileciteturn5file2L482-L500

### Why it is a disadvantage

A raw `predict_proba()` maximum can be overconfident. In this project, live traffic also cannot always reconstruct every training feature, yet the final alert confidence does not currently reflect that feature coverage.

### What our current project already has

- confidence field;
- severity field;
- feature-coverage calculation;
- threat-intelligence tags;
- alert persistence;
- dashboard table;
- model version stored with the alert.

### What we should improve

Make one unified alert score:

**calibrated confidence + feature coverage + severity + context + threat intelligence + repetition/novelty**

Then add:

- an uncertainty/abstain state;
- alert priority tiers;
- local feature explanation;
- explanation stored with the alert;
- response decisions based on risk rather than attack label alone.

### How the improvement addresses the disadvantage

Low-quality live feature reconstruction no longer produces a seemingly precise confidence score. The SOC also sees why the alert matters and which alerts deserve immediate attention.

### Why this makes the project stand out

This combines three areas that are often evaluated separately:

> **model reliability + telemetry quality + SOC prioritization**.

That is more distinctive than adding SHAP alone.

### How we can experimentally prove it

Measure:

- calibration error/ECE;
- Brier score;
- precision at top-k prioritized alerts;
- analyst alerts per hour;
- FP reduction after risk thresholding;
- confidence degradation as live feature coverage decreases;
- explanation stability under small input changes.

---

## Contribution 4 — Verified closed-loop automated response and recovery

### Problem in existing research

The literature is moving from passive detection to IPS/SOAR-style autonomous response, but safe and measurable operational response remains a challenge. The primary paper explicitly discusses this shift and points toward dynamic response. fileciteturn1file1L126-L149

### Why it is a disadvantage

An IDS that detects an attack but cannot safely contain or verify it still leaves a gap between classification and operational defense.

### What our current project already has

- automatic response trigger;
- severity-based response policies;
- response execution framework;
- response history;
- alert status updates;
- rollback support;
- incident generation.

### What we should improve

Turn existing infrastructure into a **risk-gated and verification-gated response cycle**:

1. only act automatically above a calibrated risk threshold;
2. use bounded/reversible playbooks;
3. verify whether malicious traffic falls after action;
4. rollback false-positive actions;
5. verify service/host recovery;
6. feed the outcome back into monitoring and later model evaluation.

### How the improvement addresses the disadvantage

The system stops treating “action executed” as equivalent to “threat contained.” It measures whether the response actually changed the security state.

### Why this makes the project stand out

The distinctive claim becomes:

> **Detection is connected to measurable containment and recovery.**

That is substantially closer to a real SOC than a standalone IDS classifier.

### How we can experimentally prove it

Use controlled attacks and compare:

- no-response baseline;
- current automated response;
- risk-gated verified response.

Measure detection time, containment time, response success rate, false-block rate, rollback success and recovery time.

---

# 11. What about robustness and adversarial attacks?

This should be a **secondary experiment**, not the first architectural change.

The PDF identifies adversarial robustness as an important unresolved issue and recommends explicit robustness testing. fileciteturn5file1L418-L443

The project currently has no demonstrated adversarial evaluation or adversarial-training stage in the deployed pipeline.

A practical project-compatible experiment is:

- create controlled perturbations of selected flow features within realistic constraints;
- compare prediction stability before/after perturbation;
- measure attack evasion rate;
- identify which features are most sensitive;
- use the result as a model-promotion gate.

The important contribution is **robustness measurement**, not simply saying “we used adversarial training.”

---

# 12. What about continuous monitoring and self-healing?

## Current state

The project already performs continuous capture/flow processing and has system metrics, alert statistics, monitoring deployment, and response hooks.

## Missing state

There is no demonstrated adaptive loop that says:

> traffic distribution changed → model confidence degraded → drift confirmed → model candidate retrained → candidate validated → candidate promoted → old model retained for rollback.

Nor is there a verified self-healing loop that proves a response changed the security state.

## Research-worthy version

Add **safe adaptive model lifecycle management**:

- monitor drift and confidence degradation;
- trigger an evaluation/training candidate;
- require leakage-free validation and robustness checks;
- promote only if the candidate passes thresholds;
- keep the previous artifact as rollback;
- record model version, evaluation metrics and promotion reason.

This is especially relevant because the 2026 PDF material explicitly identifies model update frequency and resilience to concept drift as deployment gaps. fileciteturn5file2L492-L500

---

# 13. Practical research roadmap without redesigning the project

## Phase 1 — Fix the scientific baseline

1. Correct the SMOTE-before-split issue.
2. Retain rare classes where possible.
3. Report MCC, FPR, FNR, PR-AUC, per-class recall and macro-F1.
4. Recreate the current v2 Random Forest as the clean baseline.

**Output:** a defensible baseline paper result.

## Phase 2 — Prove generalization

1. Add an external dataset using a harmonized feature subset.
2. Add chronological evaluation.
3. Add held-out attack-family experiments.
4. Measure unknown/OOD rejection.

**Output:** evidence that the project is not only a CIC-IDS2017 memorizer.

## Phase 3 — Make the SOC decision layer research-grade

1. Calibrate confidence.
2. Incorporate feature coverage.
3. Create contextual risk scoring.
4. Prioritize alerts.
5. Attach an interpretable explanation to important alerts.

**Output:** confidence-aware, explainable SOC triage.

## Phase 4 — Close the response loop

1. Gate automatic actions with risk.
2. Verify containment.
3. Validate rollback.
4. Measure end-to-end response latency.
5. Track recovery outcome.

**Output:** detection-to-containment research contribution.

## Phase 5 — Optional robustness/adaptation study

1. adversarial/evasion evaluation;
2. drift monitoring;
3. safe model promotion/rollback;
4. long-duration deployment testing.

**Output:** resilience and adaptive-deployment contribution.

---

# 14. Suggested experimental comparison matrix

| Experiment | Baseline | Improved system | Main proof |
|---|---|---|---|
| Leakage test | Current SMOTE-before-split | Split-before-resampling | Whether existing accuracy was inflated |
| Imbalance | Current balancing | Train-only balancing + rare-class strategy | Minority recall, FNR, MCC, PR-AUC |
| False alarms | Current classifier threshold | Calibrated/risk threshold | FPR and alert burden |
| Generalization | CIC-only holdout | Cross-dataset | Performance degradation under domain shift |
| Zero-day | Closed-set classifier | Held-out attack family + OOD/abstain | Unknown detection rate |
| Temporal robustness | Random holdout | Time-aware split | Performance under traffic evolution |
| Explainability | No explanation | Local feature explanation | Fidelity/stability and analyst usefulness |
| Deployment | Classification latency only | Sustained traffic test | p95 latency, throughput, CPU/RAM |
| Response | Simulation/manual baseline | Risk-gated verified response | Containment success and response latency |
| Recovery | Action result only | Post-action verification + rollback | Recovery correctness / false-block safety |

---

# 15. What should NOT be claimed yet

These claims are not supported by the current code alone and should not appear in the paper without the corresponding experiment:

- **“Zero-day attacks are detected.”** The current trained models are closed-set six-class classifiers.
- **“The model generalizes to real networks.”** No external-dataset validation is currently demonstrated.
- **“The 98.56% result is a leakage-free test result.”** The multiclass pipeline applies SMOTE before the split.
- **“The platform provides real self-healing.”** Several response actions are simulation-only or placeholder mechanisms.
- **“Confidence is calibrated.”** Current confidence is the maximum predicted class probability.
- **“The system is fully explainable.”** The operational prediction path currently has no SHAP/LIME explanation layer.
- **“The model is adversarially robust.”** No adversarial robustness evaluation is present in the current pipeline.

This honesty is important because the paper itself argues that standardized, transparent evaluation is needed to prevent overly optimistic IDS claims. fileciteturn5file2L527-L542

---

# 16. Final 4 strongest research contributions

If the project needs a compact contribution list for a paper, the strongest version is:

### 1. Leakage-free minority-aware detection and evaluation

A corrected training/evaluation pipeline that preserves an untouched imbalanced test set and explicitly optimizes/records rare-attack performance.

### 2. Cross-dataset and explicit unseen-attack generalization

A CIC-IDS2017-trained model evaluated across datasets, time windows and held-out attack families with an explicit unknown/abstain state.

### 3. Confidence- and feature-coverage-aware explainable risk scoring

A calibrated risk layer that combines model confidence, live feature coverage, attack severity and contextual evidence, with explanations attached to operational alerts.

### 4. Verified closed-loop response and recovery

A risk-gated response engine that not only executes an action but verifies containment, supports rollback, and measures recovery.

These four contributions are stronger together than replacing Random Forest with a more fashionable architecture because they directly answer the gaps repeatedly identified in the 2026 literature: imbalance, false alarms, unknown threats, generalization, explainability, robustness, and real-world deployment. fileciteturn5file0L22-L97

---

# 17. One strong research statement

> **Our project stands out from existing research because it converts a benchmark-trained IDS into a deployment-aware, confidence- and evidence-driven closed-loop security system, while experimentally validating leakage-free minority-attack performance, cross-dataset and unseen-attack generalization, uncertainty-aware alert prioritization, explainability, and verified automated response instead of relying on benchmark accuracy alone.**

---

# 18. Key source evidence

## Primary 2026 review in the uploaded PDF

Poltoratskyi, V., & Gavrylenko, S. **The Evolution of Intrusion Detection Systems: A Comprehensive Review of Modern Datasets, Deep Learning Approaches, and Architectural Challenges.** Advanced Information Systems, 2026, Vol. 10, No. 2.

Relevant PDF evidence:

- abstract: benchmark accuracy >98% while class imbalance, novel threats, scalability and privacy remain unresolved; real-world validation and zero-day protection are needed. fileciteturn0file0L9-L29
- challenges/open issues: false positives, imbalance, zero-day/adversarial generalization, encryption, concept drift and deployment. fileciteturn5file0L22-L66
- research gaps: lack of dynamic/adversarial/full-lifecycle evaluation, controlled experiments, and mature XAI. fileciteturn5file0L78-L97
- future directions: XAI, dynamic response, dynamic datasets, MITRE ATT&CK lifecycle scenarios, transfer/domain adaptation, multimodal data and adversarial robustness benchmarks. fileciteturn5file0L98-L135
- conclusion: benchmark accuracy is not enough; real-world application remains limited by imbalance, adversarial attacks, heterogeneous data and model opacity. fileciteturn5file0L157-L250

## Recent 2026 corroborating literature contained in the same PDF

Komal, A., & Li, S. **Intrusion Detection in the Internet of Things: A Comprehensive Review of Techniques, Architectures, Datasets, and Emerging Trends.** Sensors, 2026, 26, 3405. The paper explicitly emphasizes dataset realism, adversarial robustness, scalability, privacy, validation strategy, XAI, TinyML and deployment feasibility. fileciteturn7file1L71-L97

Guntoro, G. **Intrusion Detection Systems Research in Network Security: A Biblioshiny Based Web of Science Study, 2014 to 2026.** International Journal of Robotics and Control Systems, 2026, Vol. 6, No. 3. It highlights benchmark dependence, cross-dataset/temporal evaluation, interpretability, deployment metrics, robustness and standardized reporting. fileciteturn5file2L472-L500 fileciteturn5file2L527-L542

---

# 19. Actual project evidence used in this comparison

The following source locations were inspected in the ZIP:

- `ids-platform/README.md` — project scope, implemented modules, deployment capabilities and explicitly documented limitations.
- `ids-platform/backend/ml/training.py` — binary/multiclass preparation, class filtering, SMOTE ordering, train/test split, and model training.
- `ids-platform/backend/ml/preprocessing.py` and `backend/ml/constants.py` — CIC-IDS2017 loading and label mapping.
- `ids-platform/backend/ml/confidence.py` — current confidence definition.
- `ids-platform/backend/ml/evaluation.py` — current evaluation metrics.
- `ids-platform/backend/ml/severity.py` — current attack-label severity mapping.
- `ids-platform/backend/ml/inference.py` — deployed inference path.
- `ids-platform/backend/packet_capture/feature_mapper.py` — live-feature coverage and default filling.
- `ids-platform/backend/detection/detector.py` and `detection_service.py` — live classification path and alert generation.
- `ids-platform/backend/services/alert_service.py` — persistence, enrichment and response callback integration.
- `ids-platform/backend/response_engine/response_service.py` — automatic response workflow and rollback support.
- `ids-platform/backend/response_engine/config/response_rules.yaml` — default severity-driven response policy; simulation mode is enabled by default.
- `ids-platform/backend/response_engine/quarantine.py` and `recovery.py` — current simulation/placeholder limitations in recovery actions.
- `ids-platform/backend/database/models.py` — alert, response-history, model metadata and incident records.
- `ids-platform/frontend/src/components/alerts/AlertsTable.tsx` — current operational alert columns: severity and confidence are shown, but explanation/risk/feature-coverage evidence is not.
- `ids-platform/frontend/src/pages/Models.tsx` — versioned model display and accuracy reporting.
- `ids-platform/models/v1`–`v4` — actual trained artifacts and metadata.

---

## Bottom line

Do **not** redesign the project around a new deep-learning architecture yet.

The highest-value path is to strengthen the system that already exists:

**fix evaluation leakage → retain rare attacks → prove cross-dataset/unknown generalization → calibrate confidence and incorporate live feature coverage → add explanations and risk prioritization → verify automated containment and recovery.**

That creates a research contribution with a clear causal chain from a documented literature gap to a measurable improvement in the existing implementation.

# Model Card — p09-attrition-gb (Project 12)

**Status:** Validated synthetic-data candidate; **NOT APPROVED FOR LIVE CLOUD SERVING**.

## Intended purpose

Demonstrate an auditable MLOps lifecycle for a fitted Project 9 gradient-boosting classifier predicting a synthetic employee attrition event within 90 days. Project 12 reproduces the original model predictions, provides authenticated FastAPI real-time and batch serving locally, MLflow versioning, and offline monitoring and release-review exercises.

**This is a portfolio engineering system, not an employment decision-support service.** Do not apply predictions to real people, employee screening, disciplinary decisions, hiring, or employee retention interventions. The synthetic evidence does not establish real-world reliability.

## Model identification and provenance

| Property | Locked evidence |
|---|---|
| MLflow registered name / version | `p09-attrition-gb` / `1` |
| Source project | `09_ai_attrition_prediction` (validated Project 9 artifacts) |
| Model class | `GradientBoostingClassifier` within fitted preprocessing `Pipeline` |
| Source data | Synthetic workforce snapshot records |
| Predicted target | `attrition_within_90_days` |
| Features | 19, including 14 numeric and 5 categorical |
| Operating threshold | 0.125; selected on validation, not test |
| Model SHA-256 (Project 12 candidate) | `27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43` |
| Final test sample | 507 snapshots |
| Test prediction parity | Maximum difference approximately 1.11 × 10^-16 locally |
| Cloud release | Blocked; independent review pending |

## Frozen historical test metrics (Project 9, not a new production evaluation)

| Metric | Value |
|---|---:|
| ROC-AUC | 0.615624 |
| PR-AUC | 0.199420 |
| Brier score | 0.087186 |
| Precision | 0.161017 |
| Recall | 0.380000 |
| F1 | 0.226190 |

Confusion matrix (true negatives, false positives, false negatives, true positives): **358, 99, 31, 19**. These metrics reveal a relatively weak classifier and many false positives. They do not support any actual HR operational use.

## Feature, inference, and safety contract

The trained pipeline expects exactly 19 ordered named features, including categorical fields `department`, `job_family`, `job_level`, `location`, and `employment_type`. Numeric fields are described in `src/mlops_platform/schemas.py`; the API rejects missing or extra features, unknown categories, non-finite values, and out-of-contract types. The original data has no employee identifiers in model inputs. Preprocessing is the original fitted pipeline; it must not be silently refitted at serving time.

Local Docker inference uses a verified read-only model bundle. Cloud release requires verified approved model provenance and matching reference; **staging a candidate does not grant approval**. The application uses API-key authentication when enabled and privacy-safe request metadata logging. Model files use joblib/pickle serialization; deserialize only pinned, trusted artifacts, and treat SHA-256 as integrity evidence, not source authenticity.

## Monitoring, performance, and fairness limitations

CP12 uses sanitized request logs for aggregate service-level indicators. CP13 PSI/drift and historical test-performance reports are **offline synthetic exercises**, not live production telemetry. Drift alone is not evidence of declining accuracy. Proper performance monitoring would require matured labels and independent review. Subgroup diagnostic findings from Project 9 must not be extrapolated to real populations; no fairness or legal compliance certification is claimed.

## Release and retraining policy

CP14 promotion screening is deterministic and read-only, with all actual promotion or rollback operations held for independent approval. New training runs must preserve lineage, data-split policy, model metadata, evaluation, regression tests, and rollback evidence. Any AWS infrastructure and costs require an approved budget and deployment plan. See `docs/CP15_17_HANDOFF.md`.

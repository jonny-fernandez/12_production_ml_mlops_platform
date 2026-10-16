# Project 12 — Screenshot and Word Handoff Plan (CP17)

**Capture only after the corresponding technical step is complete.** Do not invent successful CI runs, AWS deployments, public URLs, or CloudWatch metrics. Redact authentication headers, API keys, email identities, AWS account identifiers, and any secret paths before saving screenshots.

Save screenshots in `screenshots/final/` using these **exact numbered PNG filenames**:

| Filename | Evidence required |
|---|---|
| `01_full_pytest_suite.png` | Final `pytest` run with visible pass/skip counts and no failures |
| `02_terraform_validation.png` | `terraform fmt -check` and `terraform validate` results |
| `03_mlflow_registered_model.png` | Registered model `p09-attrition-gb` version 1 and lineage |
| `04_docker_container_healthy.png` | Running secured Docker service with health status |
| `05_secured_prediction_parity.png` | Redacted authorization checks and frozen 507-record parity |
| `06_cp13_drift_report.png` | Synthetic CP13 report including offline evidence disclaimer |
| `07_cp16_reliability_audit.png` | Offline failure/recovery and bounded load test results |
| `08_cp15_ci_configuration.png` | Local CP15 gate output and CI YAML; explicitly label it **configuration/offline evidence, not an executed GitHub Actions run** |

Optional additional real-world evidence, ONLY if actually performed:

- `09_actual_github_actions_ci.png` — real GitHub Actions workflow run, only once one exists
- `10_live_https_endpoint.png` — genuine approved HTTPS ECS/Fargate endpoint
- `11_live_cloudwatch_dashboard.png` — genuine CloudWatch logs or metrics
- `12_aws_release_rollback_exercise.png` — real approved rollback operation and recovery

After collecting the required eight PNGs, install `python-docx` only if missing and run:

```powershell
.\.venv\Scripts\python.exe -m pip install 'python-docx==1.2.0'
.\.venv\Scripts\python.exe .\CP17_BUILD_SCREENSHOT_DOC.py --screenshots .\screenshots\final --output .\outputs\Project12_Final_Screenshot_Handoff.docx
```

The resulting Word file embeds the actual screenshots, their filenames, and brief explanations. **User confirmation that the screenshots are saved correctly is mandatory before final README, Git stage/commit, GitHub creation or push.** The actual GitHub Actions results screenshot is optional until a workflow genuinely runs. Never block the **prepublication** Word screenshot handoff on an impossible future result.

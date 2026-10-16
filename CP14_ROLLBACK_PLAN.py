"""Produce review-only ECS rollback instructions. No AWS calls, no execution."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARN_PATTERN = r"arn:aws:ecs:[a-z0-9-]+:[0-9]{12}:task-definition/[A-Za-z0-9_-]+:[0-9]+"
NAME_PATTERN = r"[A-Za-z0-9_-]{1,255}"


def make_plan(cluster: str, service: str, previous_task_definition_arn: str) -> dict:
    if not re.fullmatch(NAME_PATTERN, cluster) or not re.fullmatch(NAME_PATTERN, service):
        raise ValueError("Invalid ECS cluster or service name")
    if not re.fullmatch(ARN_PATTERN, previous_task_definition_arn):
        raise ValueError("Previous immutable task-definition ARN required")
    command = ("aws ecs update-service --region us-east-1 --cluster " + cluster +
               " --service " + service + " --task-definition " + previous_task_definition_arn)
    return {"status": "REVIEW_ONLY", "approved": False, "executed": False,
            "command_after_authorization": command,
            "requirements": ["verify AWS account", "validate previous task definition and its immutable image digest",
                              "review change approval", "verify rollback model approval", "monitor ALB readiness and all alarms",
                              "record incident and restore plan"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", default="project12-demo-cluster")
    parser.add_argument("--service", default="project12-demo-api")
    parser.add_argument("--previous-task-definition-arn", default="arn:aws:ecs:us-east-1:123456789012:task-definition/project12-demo-api:1")
    args = parser.parse_args()
    plan = make_plan(args.cluster, args.service, args.previous_task_definition_arn)
    path = ROOT / "outputs" / "cp14_rollback_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print("CP14 ROLLBACK PLAN CREATED (EXAMPLE VALUES, REVIEW ONLY)")
    print("No AWS calls, no model promotions, no ECS changes.")
    print("Saved:", path)
    print("RESULT: CP14 ROLLBACK PLAN PREPARED — NOT EXECUTED")


if __name__ == "__main__":
    main()

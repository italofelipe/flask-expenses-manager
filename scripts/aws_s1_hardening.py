#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

DEFAULT_PROFILE = "auraxis-admin"
DEFAULT_REGION = "us-east-1"


@dataclass(frozen=True)
class CheckResult:
    status: str
    check: str
    resource: str
    details: str


class AwsCliError(RuntimeError):
    pass


def _run_aws(
    *,
    profile: str,
    region: str,
    args: list[str],
    expect_json: bool = True,
    allow_error: bool = False,
) -> Any:
    command = [
        "aws",
        "--profile",
        profile,
        "--region",
        region,
        *args,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 and not allow_error:
        stderr = (completed.stderr or "").strip() or "unknown AWS CLI error"
        raise AwsCliError(f"{' '.join(command)} failed: {stderr}")
    if not expect_json:
        return completed
    stdout = (completed.stdout or "").strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AwsCliError(
            f"Invalid JSON returned by AWS CLI for command: {' '.join(command)}"
        ) from exc


def _describe_instances(
    *,
    profile: str,
    region: str,
    instance_ids: list[str],
) -> list[dict[str, Any]]:
    args = ["ec2", "describe-instances"]
    if instance_ids:
        args.extend(["--instance-ids", *instance_ids])
    payload = _run_aws(profile=profile, region=region, args=args)
    instances: list[dict[str, Any]] = []
    for reservation in payload.get("Reservations", []):
        instances.extend(reservation.get("Instances", []))
    return instances


def _describe_security_group(
    *,
    profile: str,
    region: str,
    group_id: str,
) -> dict[str, Any]:
    payload = _run_aws(
        profile=profile,
        region=region,
        args=[
            "ec2",
            "describe-security-groups",
            "--group-ids",
            group_id,
        ],
    )
    groups = payload.get("SecurityGroups", [])
    if not groups:
        raise AwsCliError(f"Security group not found: {group_id}")
    return groups[0]


def _describe_instance_attribute(
    *,
    profile: str,
    region: str,
    instance_id: str,
    attribute: str,
) -> dict[str, Any]:
    return _run_aws(
        profile=profile,
        region=region,
        args=[
            "ec2",
            "describe-instance-attribute",
            "--instance-id",
            instance_id,
            "--attribute",
            attribute,
        ],
    )


def _is_world_open(cidr: str) -> bool:
    return cidr in {"0.0.0.0/0", "::/0"}


def _extract_name(instance: dict[str, Any]) -> str:
    for tag in instance.get("Tags", []):
        if str(tag.get("Key")) == "Name":
            return str(tag.get("Value", ""))
    return ""


def _build_resource_name(instance: dict[str, Any]) -> tuple[str, str]:
    instance_id = str(instance.get("InstanceId", "unknown"))
    instance_name = _extract_name(instance)
    if instance_name:
        return instance_id, f"{instance_id} ({instance_name})"
    return instance_id, instance_id


def _load_ssm_managed_instance_ids(*, profile: str, region: str) -> set[str]:
    ssm_info = _run_aws(
        profile=profile,
        region=region,
        args=["ssm", "describe-instance-information"],
        allow_error=True,
    )
    if not isinstance(ssm_info, dict):
        return set()
    return {
        str(item.get("InstanceId"))
        for item in ssm_info.get("InstanceInformationList", [])
        if item.get("PingStatus") == "Online"
    }


def _append_metadata_checks(
    *,
    results: list[CheckResult],
    resource_name: str,
    metadata: dict[str, Any],
) -> None:
    if metadata.get("HttpTokens") == "required":
        results.append(
            CheckResult("PASS", "IMDSv2 required", resource_name, "HttpTokens=required")
        )
    else:
        results.append(
            CheckResult(
                "FAIL",
                "IMDSv2 required",
                resource_name,
                "HttpTokens is not required",
            )
        )

    if metadata.get("HttpEndpoint") == "enabled":
        results.append(
            CheckResult(
                "PASS",
                "Instance metadata endpoint enabled",
                resource_name,
                "HttpEndpoint=enabled",
            )
        )
        return
    results.append(
        CheckResult(
            "WARN",
            "Instance metadata endpoint enabled",
            resource_name,
            "HttpEndpoint disabled",
        )
    )


def _append_termination_check(
    *,
    profile: str,
    region: str,
    results: list[CheckResult],
    resource_name: str,
    instance_id: str,
) -> None:
    termination_payload = _describe_instance_attribute(
        profile=profile,
        region=region,
        instance_id=instance_id,
        attribute="disableApiTermination",
    )
    termination_value = (
        termination_payload.get("DisableApiTermination", {}) or {}
    ).get("Value")
    if bool(termination_value):
        results.append(
            CheckResult("PASS", "Termination protection", resource_name, "enabled")
        )
        return
    results.append(
        CheckResult("WARN", "Termination protection", resource_name, "disabled")
    )


def _append_iam_and_ssm_checks(
    *,
    results: list[CheckResult],
    resource_name: str,
    instance_id: str,
    instance: dict[str, Any],
    managed_ids: set[str],
) -> None:
    iam_profile = instance.get("IamInstanceProfile")
    if iam_profile and iam_profile.get("Arn"):
        results.append(
            CheckResult("PASS", "IAM instance profile", resource_name, "attached")
        )
    else:
        results.append(
            CheckResult("WARN", "IAM instance profile", resource_name, "missing")
        )

    if instance_id in managed_ids:
        results.append(
            CheckResult("PASS", "SSM managed instance", resource_name, "online")
        )
    else:
        results.append(
            CheckResult(
                "WARN",
                "SSM managed instance",
                resource_name,
                "not online/registered",
            )
        )


def _append_ebs_encryption_checks(
    *,
    profile: str,
    region: str,
    results: list[CheckResult],
    resource_name: str,
    instance: dict[str, Any],
) -> None:
    volume_ids: list[str] = []
    for mapping in instance.get("BlockDeviceMappings", []):
        ebs = mapping.get("Ebs") or {}
        volume_id = str(ebs.get("VolumeId", "")).strip()
        if volume_id:
            volume_ids.append(volume_id)

    if not volume_ids:
        results.append(
            CheckResult("WARN", "EBS encryption", resource_name, "no ebs volumes found")
        )
        return

    volumes_payload = _run_aws(
        profile=profile,
        region=region,
        args=["ec2", "describe-volumes", "--volume-ids", *volume_ids],
        allow_error=True,
    )
    volumes_by_id: dict[str, dict[str, Any]] = {
        str(v.get("VolumeId")): v for v in (volumes_payload.get("Volumes") or [])
    }

    for volume_id in volume_ids:
        resource = f"{resource_name}:{volume_id}"
        volume = volumes_by_id.get(volume_id)
        if not volume:
            results.append(
                CheckResult(
                    "WARN",
                    "EBS encryption",
                    resource,
                    "volume not found in describe-volumes result",
                )
            )
            continue
        if bool(volume.get("Encrypted")):
            results.append(
                CheckResult("PASS", "EBS encryption", resource, "encrypted=true")
            )
        else:
            results.append(
                CheckResult("FAIL", "EBS encryption", resource, "encrypted=false")
            )


def _permission_is_world_open(permission: dict[str, Any]) -> bool:
    ipv4_ranges = [
        str(item.get("CidrIp", "")) for item in permission.get("IpRanges", [])
    ]
    ipv6_ranges = [
        str(item.get("CidrIpv6", "")) for item in permission.get("Ipv6Ranges", [])
    ]
    return any(_is_world_open(item) for item in ipv4_ranges + ipv6_ranges)


def _classify_sg_permission(permission: dict[str, Any]) -> tuple[str, str]:
    from_port = permission.get("FromPort")
    to_port = permission.get("ToPort")
    protocol = str(permission.get("IpProtocol", ""))
    is_ssh = protocol == "tcp" and from_port == 22 and to_port == 22
    world_open = _permission_is_world_open(permission)
    if not world_open:
        if is_ssh:
            return "WARN", "SSH ingress present (prefer SSM Session Manager)"
        return "PASS", "No world-open rule found for this permission"

    is_all_ports = protocol in {"-1", "all"} or (
        protocol == "tcp" and from_port in {0, None} and to_port in {65535, None}
    )
    if is_ssh:
        return "FAIL", "Port 22 open to world"
    if is_all_ports:
        return "FAIL", "All ports open to world"
    return (
        "WARN",
        (
            "Public ingress "
            f"protocol={protocol} from_port={from_port} to_port={to_port}"
        ),
    )


def _append_security_group_checks(
    *,
    profile: str,
    region: str,
    results: list[CheckResult],
    resource_name: str,
    instance: dict[str, Any],
) -> None:
    for sg in instance.get("SecurityGroups", []):
        sg_id = str(sg.get("GroupId", ""))
        if not sg_id:
            continue
        sg_payload = _describe_security_group(
            profile=profile,
            region=region,
            group_id=sg_id,
        )
        for permission in sg_payload.get("IpPermissions", []):
            status, details = _classify_sg_permission(permission)
            if status == "FAIL" and "Port 22" in details:
                check = "Security Group SSH exposure"
            elif status == "WARN" and "SSH ingress present" in details:
                check = "Security Group SSH ingress"
            elif status == "FAIL":
                check = "Security Group broad exposure"
            elif status == "WARN":
                check = "Security Group public ingress"
            else:
                check = "Security Group ingress scope"
            results.append(
                CheckResult(status, check, f"{resource_name}:{sg_id}", details)
            )


def _append_instance_checks(
    *,
    profile: str,
    region: str,
    results: list[CheckResult],
    instance: dict[str, Any],
    managed_ids: set[str],
) -> None:
    instance_id, resource_name = _build_resource_name(instance)
    metadata = instance.get("MetadataOptions", {})
    _append_metadata_checks(
        results=results,
        resource_name=resource_name,
        metadata=metadata,
    )
    _append_termination_check(
        profile=profile,
        region=region,
        results=results,
        resource_name=resource_name,
        instance_id=instance_id,
    )
    _append_iam_and_ssm_checks(
        results=results,
        resource_name=resource_name,
        instance_id=instance_id,
        instance=instance,
        managed_ids=managed_ids,
    )
    _append_ebs_encryption_checks(
        profile=profile,
        region=region,
        results=results,
        resource_name=resource_name,
        instance=instance,
    )
    _append_security_group_checks(
        profile=profile,
        region=region,
        results=results,
        resource_name=resource_name,
        instance=instance,
    )


def _collect_s1_checks(
    *,
    profile: str,
    region: str,
    instances: list[dict[str, Any]],
) -> list[CheckResult]:
    results: list[CheckResult] = []
    managed_ids = _load_ssm_managed_instance_ids(profile=profile, region=region)

    for instance in instances:
        _append_instance_checks(
            profile=profile,
            region=region,
            results=results,
            instance=instance,
            managed_ids=managed_ids,
        )

    if not instances:
        results.append(
            CheckResult(
                "WARN",
                "Instance discovery",
                "account",
                "No EC2 instances found in selected scope",
            )
        )
    return results


def _print_results(results: list[CheckResult]) -> int:
    fail_count = 0
    warn_count = 0
    pass_count = 0
    for result in results:
        if result.status == "FAIL":
            fail_count += 1
        elif result.status == "WARN":
            warn_count += 1
        else:
            pass_count += 1
        print(
            (
                f"[{result.status}] {result.check} "
                f"| resource={result.resource} | {result.details}"
            )
        )
    print("\nSummary: " f"PASS={pass_count} WARN={warn_count} FAIL={fail_count}")
    return 1 if fail_count > 0 else 0


def _enforce_imdsv2(
    *,
    profile: str,
    region: str,
    instance_id: str,
    dry_run: bool,
) -> None:
    args = [
        "ec2",
        "modify-instance-metadata-options",
        "--instance-id",
        instance_id,
        "--http-tokens",
        "required",
        "--http-endpoint",
        "enabled",
    ]
    if dry_run:
        args.append("--dry-run")
    completed = _run_aws(
        profile=profile,
        region=region,
        args=args,
        expect_json=False,
        allow_error=True,
    )
    stderr = (completed.stderr or "").strip()
    if completed.returncode == 0:
        print(f"[APPLY] IMDSv2 enforced on {instance_id}")
        return
    if "DryRunOperation" in stderr:
        print(f"[DRY-RUN] IMDSv2 enforce validated for {instance_id}")
        return
    if "IncorrectInstanceState" in stderr:
        print(f"[WARN] {instance_id}: {stderr}")
        return
    raise AwsCliError(f"Failed enforcing IMDSv2 on {instance_id}: {stderr}")


def _set_termination_protection(
    *,
    profile: str,
    region: str,
    instance_id: str,
    dry_run: bool,
) -> None:
    args = [
        "ec2",
        "modify-instance-attribute",
        "--instance-id",
        instance_id,
        "--disable-api-termination",
        '{"Value":true}',
    ]
    if dry_run:
        args.append("--dry-run")
    completed = _run_aws(
        profile=profile,
        region=region,
        args=args,
        expect_json=False,
        allow_error=True,
    )
    stderr = (completed.stderr or "").strip()
    if completed.returncode == 0:
        print(f"[APPLY] Termination protection enabled on {instance_id}")
        return
    if "DryRunOperation" in stderr:
        print(f"[DRY-RUN] Termination protection validated for {instance_id}")
        return
    raise AwsCliError(
        f"Failed enabling termination protection on {instance_id}: {stderr}"
    )


def _run_sg_update(
    *,
    profile: str,
    region: str,
    group_id: str,
    action: str,
    permissions: list[dict[str, Any]],
    dry_run: bool,
) -> subprocess.CompletedProcess[str]:
    args = [
        "ec2",
        action,
        "--group-id",
        group_id,
        "--ip-permissions",
        json.dumps(permissions),
    ]
    if dry_run:
        args.append("--dry-run")
    return _run_aws(
        profile=profile,
        region=region,
        args=args,
        expect_json=False,
        allow_error=True,
    )


def _handle_sg_update_result(
    *,
    completed: subprocess.CompletedProcess[str],
    ok_message: str,
    dry_run_message: str,
    duplicate_message: str | None = None,
    error_context: str,
) -> None:
    stderr = (completed.stderr or "").strip()
    if completed.returncode == 0:
        print(ok_message)
        return
    if "DryRunOperation" in stderr:
        print(dry_run_message)
        return
    if duplicate_message and "InvalidPermission.Duplicate" in stderr:
        print(duplicate_message)
        return
    raise AwsCliError(f"{error_context}: {stderr}")


def _iter_world_open_ssh_cidrs(payload: dict[str, Any]) -> list[str]:
    cidrs: list[str] = []
    for permission in payload.get("IpPermissions", []):
        protocol = str(permission.get("IpProtocol", ""))
        from_port = permission.get("FromPort")
        to_port = permission.get("ToPort")
        if protocol != "tcp" or from_port != 22 or to_port != 22:
            continue
        for item in permission.get("IpRanges", []):
            cidr = str(item.get("CidrIp", ""))
            if _is_world_open(cidr):
                cidrs.append(cidr)
    return cidrs


def _iter_ssh_permissions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    permissions: list[dict[str, Any]] = []
    for permission in payload.get("IpPermissions", []):
        protocol = str(permission.get("IpProtocol", ""))
        from_port = permission.get("FromPort")
        to_port = permission.get("ToPort")
        if protocol != "tcp" or from_port != 22 or to_port != 22:
            continue
        ipv4 = [
            {"CidrIp": str(item.get("CidrIp", ""))}
            for item in permission.get("IpRanges", [])
            if str(item.get("CidrIp", "")).strip()
        ]
        ipv6 = [
            {"CidrIpv6": str(item.get("CidrIpv6", ""))}
            for item in permission.get("Ipv6Ranges", [])
            if str(item.get("CidrIpv6", "")).strip()
        ]
        if not ipv4 and not ipv6:
            continue
        perm: dict[str, Any] = {
            "IpProtocol": "tcp",
            "FromPort": 22,
            "ToPort": 22,
        }
        if ipv4:
            perm["IpRanges"] = ipv4
        if ipv6:
            perm["Ipv6Ranges"] = ipv6
        permissions.append(perm)
    return permissions


def _harden_ssh_ingress(
    *,
    profile: str,
    region: str,
    group_id: str,
    trusted_ssh_cidrs: list[str],
    dry_run: bool,
) -> None:
    payload = _describe_security_group(
        profile=profile, region=region, group_id=group_id
    )
    for cidr in _iter_world_open_ssh_cidrs(payload):
        completed = _run_sg_update(
            profile=profile,
            region=region,
            group_id=group_id,
            action="revoke-security-group-ingress",
            permissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": cidr}],
                }
            ],
            dry_run=dry_run,
        )
        _handle_sg_update_result(
            completed=completed,
            ok_message=f"[APPLY] Revoked SSH world ingress {cidr} from {group_id}",
            dry_run_message=(
                f"[DRY-RUN] Revoke SSH world ingress {cidr} from {group_id}"
            ),
            error_context=f"Failed revoking SSH ingress on {group_id}",
        )

    for cidr in trusted_ssh_cidrs:
        completed = _run_sg_update(
            profile=profile,
            region=region,
            group_id=group_id,
            action="authorize-security-group-ingress",
            permissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": cidr}],
                }
            ],
            dry_run=dry_run,
        )
        _handle_sg_update_result(
            completed=completed,
            ok_message=f"[APPLY] Authorized SSH ingress {cidr} on {group_id}",
            dry_run_message=f"[DRY-RUN] Authorize SSH ingress {cidr} on {group_id}",
            duplicate_message=(
                f"[SKIP] SSH ingress {cidr} already present on {group_id}"
            ),
            error_context=f"Failed authorizing SSH ingress on {group_id}",
        )


def _disable_ssh_ingress(
    *,
    profile: str,
    region: str,
    group_id: str,
    dry_run: bool,
) -> None:
    payload = _describe_security_group(
        profile=profile, region=region, group_id=group_id
    )
    ssh_permissions = _iter_ssh_permissions(payload)
    if not ssh_permissions:
        print(f"[SKIP] No SSH ingress rules found on {group_id}")
        return
    for perm in ssh_permissions:
        completed = _run_sg_update(
            profile=profile,
            region=region,
            group_id=group_id,
            action="revoke-security-group-ingress",
            permissions=[perm],
            dry_run=dry_run,
        )
        _handle_sg_update_result(
            completed=completed,
            ok_message=f"[APPLY] Revoked SSH ingress on {group_id}",
            dry_run_message=f"[DRY-RUN] Revoke SSH ingress on {group_id}",
            error_context=f"Failed revoking SSH ingress on {group_id}",
        )


def cmd_audit(args: argparse.Namespace) -> int:
    instances = _describe_instances(
        profile=args.profile,
        region=args.region,
        instance_ids=args.instance_ids,
    )
    results = _collect_s1_checks(
        profile=args.profile,
        region=args.region,
        instances=instances,
    )
    return _print_results(results)


def cmd_apply(args: argparse.Namespace) -> int:
    instances = _describe_instances(
        profile=args.profile,
        region=args.region,
        instance_ids=args.instance_ids,
    )
    if not instances:
        print("No instances found for selected scope.")
        return 0

    dry_run = not args.execute
    trusted_ssh_cidrs = [
        item.strip() for item in args.trusted_ssh_cidrs if item.strip()
    ]
    if args.disable_ssh and args.restrict_ssh:
        print(
            "Choose either --disable-ssh or --restrict-ssh, not both.", file=sys.stderr
        )
        return 2
    if args.restrict_ssh and not trusted_ssh_cidrs:
        print(
            (
                "When using --restrict-ssh you must provide "
                "at least one --trusted-ssh-cidr."
            ),
            file=sys.stderr,
        )
        return 2

    for instance in instances:
        _apply_instance_controls(
            args=args,
            instance=instance,
            dry_run=dry_run,
            trusted_ssh_cidrs=trusted_ssh_cidrs,
        )
    if dry_run:
        print("\nDry-run completed. Re-run with --execute to apply changes.")
    else:
        print("\nApply completed.")
    return 0


def _apply_instance_controls(
    *,
    args: argparse.Namespace,
    instance: dict[str, Any],
    dry_run: bool,
    trusted_ssh_cidrs: list[str],
) -> None:
    instance_id = str(instance.get("InstanceId"))
    _enforce_imdsv2(
        profile=args.profile,
        region=args.region,
        instance_id=instance_id,
        dry_run=dry_run,
    )
    if args.enable_termination_protection:
        _set_termination_protection(
            profile=args.profile,
            region=args.region,
            instance_id=instance_id,
            dry_run=dry_run,
        )
    _apply_ssh_controls(
        args=args,
        instance=instance,
        dry_run=dry_run,
        trusted_ssh_cidrs=trusted_ssh_cidrs,
    )


def _apply_ssh_controls(
    *,
    args: argparse.Namespace,
    instance: dict[str, Any],
    dry_run: bool,
    trusted_ssh_cidrs: list[str],
) -> None:
    if args.restrict_ssh:
        for sg in instance.get("SecurityGroups", []):
            group_id = str(sg.get("GroupId", ""))
            if not group_id:
                continue
            _harden_ssh_ingress(
                profile=args.profile,
                region=args.region,
                group_id=group_id,
                trusted_ssh_cidrs=trusted_ssh_cidrs,
                dry_run=dry_run,
            )
    if args.disable_ssh:
        for sg in instance.get("SecurityGroups", []):
            group_id = str(sg.get("GroupId", ""))
            if not group_id:
                continue
            _disable_ssh_ingress(
                profile=args.profile,
                region=args.region,
                group_id=group_id,
                dry_run=dry_run,
            )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "S1 AWS hardening helper: audit EC2 security baseline and optionally "
            "apply safe hardening controls."
        )
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"AWS CLI profile (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region (default: {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--instance-id",
        dest="instance_ids",
        action="append",
        default=[],
        help="Target EC2 instance ID. Can be repeated.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser(
        "audit",
        help="Run S1 checks and print PASS/WARN/FAIL report.",
    )
    audit_parser.set_defaults(func=cmd_audit)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply hardening controls. Uses dry-run unless --execute is provided.",
    )
    apply_parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply for real. Without this flag, the script runs dry-run mode.",
    )
    apply_parser.add_argument(
        "--enable-termination-protection",
        action="store_true",
        help="Enable termination protection on selected instances.",
    )
    apply_parser.add_argument(
        "--restrict-ssh",
        action="store_true",
        help="Revoke SSH world ingress and authorize only trusted CIDRs.",
    )
    apply_parser.add_argument(
        "--disable-ssh",
        action="store_true",
        help="Revoke all SSH ingress rules from attached security groups (prefer SSM).",
    )
    apply_parser.add_argument(
        "--trusted-ssh-cidr",
        dest="trusted_ssh_cidrs",
        action="append",
        default=[],
        help="Trusted CIDR for SSH allowlist. Can be repeated.",
    )
    apply_parser.set_defaults(func=cmd_apply)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except AwsCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Encrypt an EC2 instance root EBS volume by replacement
(snapshot -> encrypted copy -> new volume -> swap).

Notes:
- EBS encryption can't be enabled in-place on existing volumes.
- This operation requires downtime (instance stop/start).
- Defaults to dry-run; pass --execute to perform changes.
- Designed for DEV first; use carefully on PROD.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import time
from typing import Any, Sequence


@dataclasses.dataclass(frozen=True)
class RootVolumeInfo:
    instance_id: str
    root_device_name: str
    volume_id: str
    availability_zone: str
    delete_on_termination: bool


def _aws_base_args(*, profile: str | None, region: str) -> list[str]:
    args = ["aws"]
    if profile:
        args += ["--profile", profile]
    if region:
        args += ["--region", region]
    return args


def _aws_json(cmd: Sequence[str], *, profile: str | None, region: str) -> Any:
    full_cmd = [
        *_aws_base_args(profile=profile, region=region),
        *cmd,
        "--output",
        "json",
    ]
    proc = subprocess.run(full_cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"AWS CLI failed: {' '.join(full_cmd)}")
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse AWS CLI JSON output: {exc}") from exc


def _aws_wait(
    waiter: str, *, profile: str | None, region: str, args: Sequence[str]
) -> None:
    full_cmd = [
        *_aws_base_args(profile=profile, region=region),
        "ec2",
        "wait",
        waiter,
        *args,
    ]
    proc = subprocess.run(full_cmd, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"AWS waiter failed: {' '.join(full_cmd)}")


def _describe_root_volume(
    *, profile: str | None, region: str, instance_id: str
) -> RootVolumeInfo:
    resp = _aws_json(
        ["ec2", "describe-instances", "--instance-ids", instance_id],
        profile=profile,
        region=region,
    )
    reservations = resp.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        raise SystemExit(f"Instance not found: {instance_id}")

    inst = reservations[0]["Instances"][0]
    root_device_name = inst["RootDeviceName"]
    az = inst["Placement"]["AvailabilityZone"]

    mappings = inst.get("BlockDeviceMappings", [])
    root_mapping = next(
        (m for m in mappings if m.get("DeviceName") == root_device_name), None
    )
    if (
        not root_mapping
        or "Ebs" not in root_mapping
        or "VolumeId" not in root_mapping["Ebs"]
    ):
        msg = (
            f"Could not locate root EBS mapping for {instance_id} "
            f"(root device: {root_device_name})"
        )
        raise SystemExit(msg)

    return RootVolumeInfo(
        instance_id=instance_id,
        root_device_name=root_device_name,
        volume_id=root_mapping["Ebs"]["VolumeId"],
        availability_zone=az,
        delete_on_termination=bool(
            root_mapping["Ebs"].get("DeleteOnTermination", True)
        ),
    )


def _is_volume_encrypted(*, profile: str | None, region: str, volume_id: str) -> bool:
    v = _aws_json(
        ["ec2", "describe-volumes", "--volume-ids", volume_id],
        profile=profile,
        region=region,
    )["Volumes"][0]
    return bool(v.get("Encrypted"))


def _print_plan(info: RootVolumeInfo, kms_key_id: str | None) -> None:
    print("Plan:")
    print(f"- Instance: {info.instance_id}")
    print(f"- Root device: {info.root_device_name}")
    print(f"- Current root volume: {info.volume_id} (AZ={info.availability_zone})")
    print("- Steps:")
    print("  1) Stop instance (downtime)")
    print("  2) Create snapshot from current root volume")
    print(
        "  3) Copy snapshot with encryption enabled"
        + (f" (KMS={kms_key_id})" if kms_key_id else "")
    )
    print("  4) Create new encrypted volume from encrypted snapshot")
    print(
        "  5) Detach old root volume; attach new encrypted volume at same device name"
    )
    print("  6) Start instance; wait for running + status checks")
    print(
        "- Rollback: keep old volume and snapshots unless you delete "
        "them manually later."
    )


def _stop_instance(*, profile: str | None, region: str, instance_id: str) -> None:
    _aws_json(
        ["ec2", "stop-instances", "--instance-ids", instance_id],
        profile=profile,
        region=region,
    )
    _aws_wait(
        "instance-stopped",
        profile=profile,
        region=region,
        args=["--instance-ids", instance_id],
    )


def _start_instance(*, profile: str | None, region: str, instance_id: str) -> None:
    _aws_json(
        ["ec2", "start-instances", "--instance-ids", instance_id],
        profile=profile,
        region=region,
    )
    _aws_wait(
        "instance-running",
        profile=profile,
        region=region,
        args=["--instance-ids", instance_id],
    )
    # Small buffer after run/wait to let status checks stabilize.
    time.sleep(5)


def _create_snapshot(
    *, profile: str | None, region: str, volume_id: str, description: str
) -> str:
    snap = _aws_json(
        [
            "ec2",
            "create-snapshot",
            "--volume-id",
            volume_id,
            "--description",
            description,
        ],
        profile=profile,
        region=region,
    )
    snapshot_id = snap["SnapshotId"]
    _aws_wait(
        "snapshot-completed",
        profile=profile,
        region=region,
        args=["--snapshot-ids", snapshot_id],
    )
    return snapshot_id


def _copy_snapshot_encrypted(
    *,
    profile: str | None,
    region: str,
    source_snapshot_id: str,
    kms_key_id: str | None,
) -> str:
    cmd = [
        "ec2",
        "copy-snapshot",
        "--source-region",
        region,
        "--source-snapshot-id",
        source_snapshot_id,
        "--encrypted",
        "--description",
        f"Encrypted copy of {source_snapshot_id}",
    ]
    if kms_key_id:
        cmd += ["--kms-key-id", kms_key_id]
    snap = _aws_json(cmd, profile=profile, region=region)
    snapshot_id = snap["SnapshotId"]
    _aws_wait(
        "snapshot-completed",
        profile=profile,
        region=region,
        args=["--snapshot-ids", snapshot_id],
    )
    return snapshot_id


def _create_volume_from_snapshot(
    *, profile: str | None, region: str, snapshot_id: str, az: str
) -> str:
    vol = _aws_json(
        [
            "ec2",
            "create-volume",
            "--snapshot-id",
            snapshot_id,
            "--availability-zone",
            az,
            "--volume-type",
            "gp3",
        ],
        profile=profile,
        region=region,
    )
    volume_id = vol["VolumeId"]
    _aws_wait(
        "volume-available",
        profile=profile,
        region=region,
        args=["--volume-ids", volume_id],
    )
    return volume_id


def _detach_volume(
    *, profile: str | None, region: str, volume_id: str, instance_id: str
) -> None:
    _aws_json(
        [
            "ec2",
            "detach-volume",
            "--volume-id",
            volume_id,
            "--instance-id",
            instance_id,
        ],
        profile=profile,
        region=region,
    )
    _aws_wait(
        "volume-available",
        profile=profile,
        region=region,
        args=["--volume-ids", volume_id],
    )


def _attach_volume(
    *,
    profile: str | None,
    region: str,
    volume_id: str,
    instance_id: str,
    device_name: str,
) -> None:
    _aws_json(
        [
            "ec2",
            "attach-volume",
            "--volume-id",
            volume_id,
            "--instance-id",
            instance_id,
            "--device",
            device_name,
        ],
        profile=profile,
        region=region,
    )
    _aws_wait(
        "volume-in-use",
        profile=profile,
        region=region,
        args=["--volume-ids", volume_id],
    )


def _set_delete_on_termination(
    *,
    profile: str | None,
    region: str,
    instance_id: str,
    device_name: str,
    delete_on_termination: bool,
) -> None:
    payload = json.dumps(
        [
            {
                "DeviceName": device_name,
                "Ebs": {"DeleteOnTermination": delete_on_termination},
            }
        ]
    )
    _aws_json(
        [
            "ec2",
            "modify-instance-attribute",
            "--instance-id",
            instance_id,
            "--block-device-mappings",
            payload,
        ],
        profile=profile,
        region=region,
    )


def run(
    *,
    profile: str | None,
    region: str,
    instance_id: str,
    kms_key_id: str | None,
    execute: bool,
) -> int:
    info = _describe_root_volume(
        profile=profile, region=region, instance_id=instance_id
    )

    if _is_volume_encrypted(profile=profile, region=region, volume_id=info.volume_id):
        msg = (
            f"[PASS] Root volume already encrypted: {info.volume_id} "
            f"(instance {instance_id})"
        )
        print(msg)
        return 0

    _print_plan(info, kms_key_id)
    if not execute:
        print("\nDry-run mode: no changes were made. Re-run with --execute to apply.")
        return 0

    print("\nExecuting...")
    _stop_instance(profile=profile, region=region, instance_id=instance_id)

    description = f"Auraxis root volume snapshot before encryption swap ({instance_id})"
    base_snapshot_id = _create_snapshot(
        profile=profile,
        region=region,
        volume_id=info.volume_id,
        description=description,
    )
    print(f"[OK] Snapshot created: {base_snapshot_id}")

    encrypted_snapshot_id = _copy_snapshot_encrypted(
        profile=profile,
        region=region,
        source_snapshot_id=base_snapshot_id,
        kms_key_id=kms_key_id,
    )
    print(f"[OK] Encrypted snapshot created: {encrypted_snapshot_id}")

    new_volume_id = _create_volume_from_snapshot(
        profile=profile,
        region=region,
        snapshot_id=encrypted_snapshot_id,
        az=info.availability_zone,
    )
    print(f"[OK] New encrypted volume created: {new_volume_id}")

    _detach_volume(
        profile=profile,
        region=region,
        volume_id=info.volume_id,
        instance_id=instance_id,
    )
    print(f"[OK] Detached old root volume: {info.volume_id}")

    _attach_volume(
        profile=profile,
        region=region,
        volume_id=new_volume_id,
        instance_id=instance_id,
        device_name=info.root_device_name,
    )
    print(f"[OK] Attached new root volume: {new_volume_id} -> {info.root_device_name}")

    _set_delete_on_termination(
        profile=profile,
        region=region,
        instance_id=instance_id,
        device_name=info.root_device_name,
        delete_on_termination=info.delete_on_termination,
    )
    print(
        "[OK] DeleteOnTermination preserved: "
        f"{info.root_device_name}={info.delete_on_termination}"
    )

    _start_instance(profile=profile, region=region, instance_id=instance_id)
    print("[OK] Instance started.")

    print("\nPost-check:")
    # Re-read mapping to confirm.
    new_info = _describe_root_volume(
        profile=profile, region=region, instance_id=instance_id
    )
    enc = _is_volume_encrypted(
        profile=profile, region=region, volume_id=new_info.volume_id
    )
    print(f"- Root volume now: {new_info.volume_id} encrypted={enc}")
    print(
        "\nKeep the old volume and snapshots for rollback until you validate "
        "the instance is healthy."
    )
    return 0 if enc else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Encrypt EC2 root volume by replacement (downtime)."
    )
    p.add_argument("--profile", default=None, help="AWS CLI profile (optional).")
    p.add_argument(
        "--region", default="us-east-1", help="AWS region. Default: us-east-1"
    )
    p.add_argument(
        "--instance-id", required=True, help="EC2 instance id (e.g. i-xxxx)."
    )
    p.add_argument(
        "--kms-key-id",
        default=None,
        help="Optional KMS KeyId for EBS encryption (defaults to AWS-managed).",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform changes (default is dry-run).",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    return run(
        profile=args.profile,
        region=args.region,
        instance_id=args.instance_id,
        kms_key_id=args.kms_key_id,
        execute=args.execute,
    )


if __name__ == "__main__":
    raise SystemExit(main())

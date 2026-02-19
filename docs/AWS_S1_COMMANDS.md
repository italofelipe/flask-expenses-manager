# AWS S1 Commands (EC2 Hardening) - Auraxis

This document lists the operational commands used to audit and harden EC2 instances for the `S1` backlog item.

Scope:
- EC2: IMDSv2, termination protection, IAM instance profile, SSM managed status
- Network exposure: Security Groups (SSH + public ingress)
- Storage: EBS encryption checks (and migration steps)

Defaults:
- AWS profile: `auraxis-admin`
- Region: `us-east-1`

## When You Will Need This File Again

Common scenarios:
- New laptop / fresh terminal: re-login via SSO and validate identity (Section 0).
- Monthly hardening check: re-run audit to ensure nothing drifted (Section 1).
- After changing Security Groups / networking: confirm exposure (Sections 1, 7).
- Before enabling SSM features (Session Manager, Run Command, Patch Manager): ensure profile + agent are healthy (Sections 4, 5, 6).
- Security incident: quickly validate IMDSv2, SG exposure, termination protection, and SSM reachability (Sections 1, 2, 5, 7).
- Compliance hardening: migrate root disks to encrypted EBS volumes (Section 8).

## 0) Pre-req: Make Sure You Are Using SSO

When:
- Anytime you start a new terminal session or your session expires.

Commands:
```bash
aws configure list-profiles
aws sso login --profile auraxis-admin
AWS_PROFILE=auraxis-admin AWS_REGION=us-east-1 aws sts get-caller-identity
```

Expected:
- `Arn` contains `assumed-role/AWSReservedSSO_.../your-user` (not `:root`).

## 1) Audit EC2 Baseline (S1)

When:
- Before applying changes.
- After applying changes (to confirm improvement).
- During incident response / access reviews.

Command (whole account / region):
```bash
./scripts/aws_s1_hardening.py --profile auraxis-admin --region us-east-1 audit
```

Command (specific instances):
```bash
./scripts/aws_s1_hardening.py --profile auraxis-admin --region us-east-1 \
  --instance-id i-0057e3b52162f78f8 \
  --instance-id i-0bb5b392c2188dd3d \
  audit
```

## 2) Apply Safe Hardening (Dry-Run First)

When:
- After audit identifies gaps, and you want safe hardening first.

Dry-run (no changes):
```bash
./scripts/aws_s1_hardening.py --profile auraxis-admin --region us-east-1 \
  --instance-id i-0057e3b52162f78f8 \
  --instance-id i-0bb5b392c2188dd3d \
  apply --enable-termination-protection
```

Apply for real:
```bash
./scripts/aws_s1_hardening.py --profile auraxis-admin --region us-east-1 \
  --instance-id i-0057e3b52162f78f8 \
  --instance-id i-0bb5b392c2188dd3d \
  apply --enable-termination-protection --execute
```

Restrict SSH to an allowlist (example):
```bash
./scripts/aws_s1_hardening.py --profile auraxis-admin --region us-east-1 \
  --instance-id i-0057e3b52162f78f8 \
  apply --restrict-ssh --trusted-ssh-cidr 187.91.40.203/32
```

Then apply with `--execute`.

## 3) Check Instance Profile Attachment

When:
- After creating/attaching IAM instance profiles.
- Before relying on SSM/CloudWatch in production.

Command:
```bash
AWS_PROFILE=auraxis-admin AWS_REGION=us-east-1 aws ec2 describe-instances \
  --instance-ids i-0057e3b52162f78f8 i-0bb5b392c2188dd3d \
  --query 'Reservations[].Instances[].{Id:InstanceId,Name:Tags[?Key==`Name`]|[0].Value,Iam:IamInstanceProfile.Arn}' \
  --output table
```

## 4) Create IAM Role + Instance Profile (SSM + CloudWatch Agent)

When:
- When EC2 instances have no instance profile.
- Required to manage instances using AWS Systems Manager (SSM).

Commands:
```bash
export AWS_PROFILE=auraxis-admin
export AWS_REGION=us-east-1

ROLE_NAME="auraxis-ec2-ssm-role"
PROFILE_NAME="auraxis-ec2-ssm-profile"

cat > /tmp/auraxis-ec2-trust-policy.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file:///tmp/auraxis-ec2-trust-policy.json

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME"
aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME"
```

Attach to instances:
```bash
PROFILE_ARN=$(aws iam get-instance-profile \
  --instance-profile-name auraxis-ec2-ssm-profile \
  --query 'InstanceProfile.Arn' \
  --output text)

aws ec2 associate-iam-instance-profile \
  --iam-instance-profile Arn="$PROFILE_ARN" \
  --instance-id i-0057e3b52162f78f8

aws ec2 associate-iam-instance-profile \
  --iam-instance-profile Arn="$PROFILE_ARN" \
  --instance-id i-0bb5b392c2188dd3d
```

## 5) Check SSM Registration (Managed Instances)

When:
- After attaching instance profile.
- After installing/restarting `amazon-ssm-agent`.

Commands:
```bash
AWS_PROFILE=auraxis-admin AWS_REGION=us-east-1 aws ssm describe-instance-information \
  --query 'InstanceInformationList[].{Id:InstanceId,Ping:PingStatus,Agent:AgentVersion,Platform:PlatformName}' \
  --output table
```

If no instances appear:
- SSM agent may not be installed/running.
- Instance may not have outbound internet/NAT access to reach SSM endpoints.

## 6) Install/Start SSM Agent (Ubuntu on EC2)

When:
- If Section 5 returns an empty list, or `PingStatus` is not `Online`.
- Immediately after attaching the instance profile.

Run on the EC2 instance (via SSH):
```bash
sudo snap install amazon-ssm-agent --classic
sudo systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service
sudo systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service
sudo systemctl status snap.amazon-ssm-agent.amazon-ssm-agent.service --no-pager
```

Useful troubleshooting on the EC2 instance:
```bash
journalctl -u snap.amazon-ssm-agent.amazon-ssm-agent.service -n 200 --no-pager
curl -sS https://ssm.us-east-1.amazonaws.com/ >/dev/null && echo "SSM endpoint reachable"
```

## 6) EBS Encryption (Important Notes)

EBS encryption cannot be enabled in-place on an existing root volume. Typical procedure:
1. Stop instance
2. Snapshot root volume
3. Copy snapshot with encryption enabled
4. Create new encrypted volume
5. Detach old root volume, attach new one (as root device)
6. Start instance and validate boot

When:
- After you confirm a maintenance window (PROD causes downtime).
- Prefer doing DEV first.

This flow is intentionally documented-only until a dedicated automation with safety checks is implemented.

## 7) Security Group Quick Checks (Ingress)

When:
- After you update inbound rules, or if SSH times out.

List security groups attached to an instance:
```bash
AWS_PROFILE=auraxis-admin AWS_REGION=us-east-1 aws ec2 describe-instances \
  --instance-ids i-0057e3b52162f78f8 \
  --query 'Reservations[].Instances[].SecurityGroups[].{Id:GroupId,Name:GroupName}' \
  --output table
```

Dump inbound rules for a security group:
```bash
AWS_PROFILE=auraxis-admin AWS_REGION=us-east-1 aws ec2 describe-security-groups \
  --group-ids sg-XXXXXXXX \
  --query 'SecurityGroups[].IpPermissions' \
  --output json
```

## 8) EBS Root Volume Encryption (Downtime Required)

When:
- DEV first (recommended). PROD only with a maintenance window.

Find root volume id for an instance:
```bash
AWS_PROFILE=auraxis-admin AWS_REGION=us-east-1 aws ec2 describe-instances \
  --instance-ids i-0bb5b392c2188dd3d \
  --query 'Reservations[].Instances[].BlockDeviceMappings[?DeviceName==`/dev/sda1` || DeviceName==`/dev/xvda`].Ebs.VolumeId' \
  --output text
```

High-level migration steps (manual):
- Stop instance
- Snapshot root volume
- Copy snapshot with encryption
- Create new encrypted volume in the same AZ
- Detach old root volume, attach new one to the same device name
- Start instance, validate boot and services

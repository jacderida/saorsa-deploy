# saorsa-deploy

CLI tool for deploying testnets for saorsa-node using Terraform and Pyinfra.

## Project Setup

- **Language**: Python (>=3.10)
- **Package manager**: `uv`
- **Build system**: hatchling
- **Entry point**: `saorsa_deploy.main:main` (installed as `saorsa-deploy`)
- **Dependencies**: boto3, pyinfra, requests, rich
- **Dev dependencies**: pytest, ruff

## Commands

```bash
uv run saorsa-deploy infra --name NAME --node-count N --vm-count N [--attached-volume-size N] [--region-counts N,N] [--testnet]
uv run saorsa-deploy destroy --name NAME [--force]
```

## Project Structure

```
saorsa_deploy/
  main.py              # CLI entry point, argparse setup, delegates to cmd/
  cmd/
    infra.py            # infra command implementation
    destroy.py          # destroy command implementation
  bootstrap.py          # Bootstrap VM creation/destruction via DO API
  providers.py          # Provider/region config and resolution
  state.py              # Deployment state persistence (S3)
  terraform.py          # Terraform workspace prep, init, apply, destroy
  executor.py           # Parallel execution with rich progress display
resources/
  digitalocean/         # Terraform manifests (one directory per provider)
    main.tf, variables.tf, outputs.tf, provider.tf, versions.tf
tests/
  test_providers.py     # Unit tests for region resolution
  test_state.py         # Unit tests for S3 state persistence (mocked boto3)
  test_terraform.py     # Unit tests for terraform runner (mocked subprocess)
```

## Conventions

- **CLI arguments** are defined in alphabetical order in `main.py` for easy reference.
- **Command implementations** go in `saorsa_deploy/cmd/<command>.py`, not in `main.py`. Each command has a `cmd_<name>(args)` function. `main.py` stays thin and only does argparse + delegation.
- **Terraform manifests** live in `resources/<provider>/`. At runtime, they are copied to `.saorsa/workspaces/<provider>-<region>/` for parallel execution.
- **Terraform state** is stored in AWS S3, bucket `maidsafe-org-infra-tfstate`, with per-region keys like `saorsa-deploy/do-lon1.tfstate`.
- **DO_TOKEN** environment variable is used for Digital Ocean authentication (mapped to `TF_VAR_do_token` for Terraform, used directly for bootstrap VM API calls).
- **AWS credentials** are required for S3 access (deployment state and Terraform backend). boto3 uses the standard credential chain: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars, `~/.aws/credentials`, or IAM roles.
- **Deployment state**: After `infra` provisioning, metadata (name, regions, variables) is saved to `s3://maidsafe-org-infra-tfstate/saorsa-deploy/deployments/{name}.json`. The `destroy` command reads this state so users don't need to re-specify configuration. State is deleted after successful destroy.
- **Bootstrap VM**: A single VM (`{name}-saorsa-bootstrap`) is created via the DO API (not Terraform) before the main deployment. It runs in lon1, s-2vcpu-4gb, Ubuntu 24.04, with a 35GB attached volume. See `saorsa_deploy/bootstrap.py`.
- **`--name` argument**: Required. Used as a prefix for all VM names (e.g., `DEV-01-saorsa-node-lon1-1`).
- **Multi-provider/multi-region** design: one Terraform run per region, up to 5 concurrent via `ThreadPoolExecutor`.

## Testing

```bash
uv run pytest tests/ -v
```

- Tests use `@patch("saorsa_deploy.terraform.subprocess.run")` to mock Terraform calls -- do NOT inject mock callables as function parameters.
- Use `subprocess.CompletedProcess` for mock return values.
- Provider tests use fixtures with custom `ProviderConfig` instances to avoid depending on real provider data.

## Linting & Formatting

```bash
uv run ruff format saorsa_deploy/ tests/
uv run ruff check saorsa_deploy/ tests/
```

- Ruff config: line-length 100, rules E/F/I.
- Always run both format and check before committing.

## Key Design Decisions

- **Provider-per-directory Terraform structure**: Each cloud provider gets its own directory under `resources/`. TF files are copied to isolated workspace directories at runtime so parallel `terraform apply` calls don't conflict.
- **Predefined region lists**: Users specify how many regions (via `--region-counts`), not which regions. The tool picks from a predefined ordered list per provider.
- **`--testnet` flag**: Overrides to Digital Ocean only, `lon1` region only.
- **SSH keys**: Hardcoded as defaults in Terraform `variables.tf` (list of DO SSH key IDs).
- **VM naming**: 1-indexed with deployment name prefix (e.g., `DEV-01-saorsa-node-lon1-1`).
- **`destroy` command**: Reads deployment state from S3, runs `terraform destroy` in parallel, destroys bootstrap VM/volume via DO API, then deletes state. `--force` skips confirmation. Designed to work from fresh CI agents.

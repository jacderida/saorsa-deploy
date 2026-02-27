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
uv run saorsa-deploy infra --name NAME --vm-count N [--attached-volume-size N] [--region-counts N,N] [--testnet]
uv run saorsa-deploy provision-genesis --name NAME --port PORT [--node-version VER | --branch-name BR --repo-owner OWNER] [--ip-version v4|v6] [--log-level LEVEL] [--testnet]
uv run saorsa-deploy provision --name NAME --node-count N [--node-version VER | --branch-name BR --repo-owner OWNER] [--port PORT] [--region REG] [--ip-version v4|v6] [--log-level LEVEL] [--testnet]
uv run saorsa-deploy build-saorsa-node-binary --branch-name BR --repo-owner OWNER [--ssh-key-path PATH]
uv run saorsa-deploy destroy --name NAME [--force]
```

## Project Structure

```
saorsa_deploy/
  main.py              # CLI entry point, argparse setup, delegates to cmd/
  binary_source.py     # Binary URL resolution (GitHub releases + S3 custom builds)
  bootstrap.py         # Bootstrap VM creation/destruction via DO API
  build_droplet.py     # Ephemeral build VM management via DO API
  executor.py          # Parallel execution with rich progress display
  providers.py         # Provider/region config and resolution
  resources.py         # Resource directory discovery (importlib.resources)
  state.py             # Deployment state persistence (S3)
  terraform.py         # Terraform workspace prep, init, apply, destroy
  cmd/
    build.py           # build-saorsa-node-binary command implementation
    destroy.py         # destroy command implementation
    infra.py           # infra command implementation
    provision.py       # provision command implementation
    provision_genesis.py # provision-genesis command implementation
  provisioning/
    build.py           # Pyinfra operations: install Rust, clone, build, upload to S3
    genesis.py         # Pyinfra operations: install and start genesis node
    node.py            # Pyinfra operations: install and start node services
    progress.py        # Rich progress display for Pyinfra operations
  resources/
    aws-build-infra/   # Terraform manifests for S3 bucket + IAM user (build uploads)
    digitalocean/      # Terraform manifests (one directory per provider)
tests/
  test_binary_source.py           # URL resolution and existence checks
  test_binary_source_resolution.py # Argument validation for --node-version/--branch-name
  test_build.py                   # Build command flow tests
  test_build_droplet.py           # Build droplet create/destroy tests
  test_providers.py               # Region resolution tests
  test_provision.py               # Node provisioner tests
  test_provision_genesis.py       # Genesis provisioner tests
  test_state.py                   # S3 state persistence tests
  test_terraform.py               # Terraform runner tests
```

## Conventions

- **CLI arguments** are defined in alphabetical order in `main.py` for easy reference.
- **Command implementations** go in `saorsa_deploy/cmd/<command>.py`, not in `main.py`. Each command has a `cmd_<name>(args)` function. `main.py` stays thin and only does argparse + delegation.
- **Terraform manifests** live in `saorsa_deploy/resources/<provider>/` (bundled inside the package). At runtime, they are copied to `.saorsa/workspaces/<provider>-<region>/` (relative to cwd) for parallel execution.
- **Terraform state** is stored in AWS S3, bucket `maidsafe-org-infra-tfstate`, with per-region keys like `saorsa-deploy/do-lon1.tfstate`.
- **DO_TOKEN** environment variable is used for Digital Ocean authentication (mapped to `TF_VAR_do_token` for Terraform, used directly for bootstrap VM API calls).
- **AWS credentials** are required for S3 access (deployment state and Terraform backend). boto3 uses the standard credential chain: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars, `~/.aws/credentials`, or IAM roles.
- **Deployment state**: After `infra` provisioning, metadata (name, regions, variables) is saved to `s3://maidsafe-org-infra-tfstate/saorsa-deploy/deployments/{name}.json`. The `destroy` command reads this state so users don't need to re-specify configuration. State is deleted after successful destroy.
- **Bootstrap VM**: A single VM (`{name}-saorsa-bootstrap`) is created via the DO API (not Terraform) before the main deployment. It runs in lon1, s-2vcpu-4gb, Ubuntu 24.04, with a 35GB attached volume. See `saorsa_deploy/bootstrap.py`.
- **`--name` argument**: Required. Used as a prefix for all VM names (e.g., `DEV-01-saorsa-node-lon1-1`).
- **Multi-provider/multi-region** design: one Terraform run per region, up to 5 concurrent via `ThreadPoolExecutor`.
- **Binary source resolution**: Provisioning commands support three modes:
  - **Default**: Fetches latest release from GitHub (`saorsa-labs/saorsa-node`).
  - **`--node-version`**: Fetches a specific release version (e.g., `--node-version 0.2.0`).
  - **`--branch-name` + `--repo-owner`**: Uses a custom-built binary from S3 (must run `build-saorsa-node-binary` first).
  - `--node-version` and `--branch-name`/`--repo-owner` are mutually exclusive. `--branch-name` and `--repo-owner` must be used together.
- **Build droplets**: Ephemeral `c-16` (CPU-optimized) DO droplets for building saorsa-node from source. Named `saorsa-build-{owner}-{branch}`. Destroyed in a `finally` block after build completes.
- **Build binary storage**: Custom-built binaries are uploaded to S3 bucket `saorsa-node-builds` (eu-west-2) at key `builds/{repo_owner}/{branch_name}/saorsa-node`. Public read access.
- **`SAORSA_BUILD_AWS_ACCESS_KEY_ID`** / **`SAORSA_BUILD_AWS_SECRET_ACCESS_KEY`**: Required for `build-saorsa-node-binary`. Separate from standard AWS credentials. For the `saorsa-build-uploader` IAM user.

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

## Releasing

Releases use semantic versioning with git tags. The version source of truth is `pyproject.toml`.

```bash
uv run scripts/release.py <VERSION>    # e.g., uv run scripts/release.py 0.2.0
uv run saorsa-deploy --version          # Print current version
```

The release script updates `pyproject.toml`, creates a `chore(release): vX.Y.Z` commit, tags it, and pushes to the maidsafe remote (auto-detects `origin` vs `upstream`).

## Key Design Decisions

- **Provider-per-directory Terraform structure**: Each cloud provider gets its own directory under `saorsa_deploy/resources/`. TF files are copied to isolated workspace directories at runtime so parallel `terraform apply` calls don't conflict.
- **Predefined region lists**: Users specify how many regions (via `--region-counts`), not which regions. The tool picks from a predefined ordered list per provider.
- **`--testnet` flag**: Overrides to Digital Ocean only, `lon1` region only.
- **SSH keys**: Hardcoded as defaults in Terraform `variables.tf` (list of DO SSH key IDs).
- **VM naming**: 1-indexed with deployment name prefix (e.g., `DEV-01-saorsa-node-lon1-1`).
- **`destroy` command**: Reads deployment state from S3, runs `terraform destroy` in parallel, destroys bootstrap VM/volume via DO API, then deletes state. `--force` skips confirmation. Designed to work from fresh CI agents.
- **`build-saorsa-node-binary` command**: Spins up a `c-16` DO droplet, installs Rust, clones and builds saorsa-node, uploads the binary to S3, then destroys the droplet. AWS build infrastructure (S3 bucket + IAM user) is managed by Terraform in `saorsa_deploy/resources/aws-build-infra/`.
- **Binary source module** (`binary_source.py`): Central module for resolving binary download URLs. Used by both provision commands and the build command. Supports GitHub releases (archive) and S3 custom builds (raw binary).

import json

import boto3

S3_BUCKET = "maidsafe-org-infra-tfstate"
S3_REGION = "eu-west-2"
S3_KEY_PREFIX = "saorsa-deploy/deployments"


def _get_s3_client():
    return boto3.client("s3", region_name=S3_REGION)


def save_deployment_state(
    name: str,
    regions: list[tuple[str, str]],
    terraform_variables: dict[str, str],
) -> None:
    """Save deployment metadata to S3 for later use by the destroy command."""
    state = {
        "name": name,
        "regions": [[provider, region] for provider, region in regions],
        "terraform_variables": terraform_variables,
    }
    client = _get_s3_client()
    client.put_object(
        Bucket=S3_BUCKET,
        Key=f"{S3_KEY_PREFIX}/{name}.json",
        Body=json.dumps(state, indent=2),
        ContentType="application/json",
    )


def load_deployment_state(name: str) -> dict:
    """Load deployment metadata from S3.

    Returns a dict with keys: name, regions, terraform_variables.
    Raises RuntimeError if the deployment state is not found.
    """
    client = _get_s3_client()
    try:
        resp = client.get_object(
            Bucket=S3_BUCKET,
            Key=f"{S3_KEY_PREFIX}/{name}.json",
        )
        return json.loads(resp["Body"].read())
    except client.exceptions.NoSuchKey:
        raise RuntimeError(
            f"No deployment state found for '{name}'. "
            "Was this deployment created with the infra command?"
        )


def delete_deployment_state(name: str) -> None:
    """Delete deployment metadata from S3 after a successful destroy."""
    client = _get_s3_client()
    client.delete_object(
        Bucket=S3_BUCKET,
        Key=f"{S3_KEY_PREFIX}/{name}.json",
    )

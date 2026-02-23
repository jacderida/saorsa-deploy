import json
from unittest.mock import MagicMock, patch

import pytest

from saorsa_deploy.state import (
    S3_BUCKET,
    S3_KEY_PREFIX,
    delete_deployment_state,
    load_deployment_state,
    save_deployment_state,
)


@pytest.fixture
def mock_s3():
    with patch("saorsa_deploy.state.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        yield mock_client


class TestSaveDeploymentState:
    def test_puts_json_to_s3(self, mock_s3):
        save_deployment_state(
            name="DEV-01",
            regions=[("digitalocean", "lon1"), ("digitalocean", "nyc1")],
            terraform_variables={"name": "DEV-01", "vm_count": "2", "node_count": "5"},
        )

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == S3_BUCKET
        assert call_kwargs["Key"] == f"{S3_KEY_PREFIX}/DEV-01.json"
        assert call_kwargs["ContentType"] == "application/json"

        body = json.loads(call_kwargs["Body"])
        assert body["name"] == "DEV-01"
        assert body["regions"] == [["digitalocean", "lon1"], ["digitalocean", "nyc1"]]
        assert body["terraform_variables"]["vm_count"] == "2"

    def test_regions_stored_as_lists(self, mock_s3):
        save_deployment_state(
            name="TEST",
            regions=[("digitalocean", "ams3")],
            terraform_variables={},
        )

        body = json.loads(mock_s3.put_object.call_args.kwargs["Body"])
        assert body["regions"] == [["digitalocean", "ams3"]]


class TestLoadDeploymentState:
    def test_loads_json_from_s3(self, mock_s3):
        state = {
            "name": "DEV-01",
            "regions": [["digitalocean", "lon1"]],
            "terraform_variables": {"name": "DEV-01", "vm_count": "2"},
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(state).encode()
        mock_s3.get_object.return_value = {"Body": mock_body}

        result = load_deployment_state("DEV-01")

        mock_s3.get_object.assert_called_once_with(
            Bucket=S3_BUCKET,
            Key=f"{S3_KEY_PREFIX}/DEV-01.json",
        )
        assert result["name"] == "DEV-01"
        assert result["regions"] == [["digitalocean", "lon1"]]

    def test_raises_on_not_found(self, mock_s3):
        error_class = type("NoSuchKey", (Exception,), {})
        mock_s3.exceptions.NoSuchKey = error_class
        mock_s3.get_object.side_effect = error_class("not found")

        with pytest.raises(RuntimeError, match="No deployment state found"):
            load_deployment_state("NONEXISTENT")


class TestDeleteDeploymentState:
    def test_deletes_from_s3(self, mock_s3):
        delete_deployment_state("DEV-01")

        mock_s3.delete_object.assert_called_once_with(
            Bucket=S3_BUCKET,
            Key=f"{S3_KEY_PREFIX}/DEV-01.json",
        )

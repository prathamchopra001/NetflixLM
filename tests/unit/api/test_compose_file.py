"""Static checks on compose.yaml (no Docker needed): the security and pinning rules of the docs."""

from pathlib import Path

import pytest
import yaml

SERVICES = yaml.safe_load((Path(__file__).parents[3] / "compose.yaml").read_text())["services"]


def test_expected_services() -> None:
    assert {"postgres", "objectstore", "ray-head", "api", "keycloak", "mlflow"} <= set(SERVICES)


def test_published_ports_are_localhost_only() -> None:
    for name, svc in SERVICES.items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name}: {port}"


@pytest.mark.parametrize("name", ["postgres", "objectstore", "keycloak"])
def test_third_party_images_pinned_by_digest(name: str) -> None:
    assert "@sha256:" in SERVICES[name]["image"]


def test_ray_head_reserves_gpu_and_shm() -> None:
    head = SERVICES["ray-head"]
    assert head["deploy"]["resources"]["reservations"]["devices"][0]["count"] == "all"
    assert head["shm_size"] == "8gb"
    assert head["environment"]["VLLM_WSL2_ENABLE_PIN_MEMORY"] == "1"
    assert head["environment"]["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"


def test_every_long_running_service_has_a_healthcheck() -> None:
    for name, svc in SERVICES.items():
        if name != "objectstore-init":
            assert "healthcheck" in svc, name


def test_dev_realm_import_is_opt_in_by_environment() -> None:
    kc = SERVICES["keycloak"]
    assert kc["environment"]["NIP_KEYCLOAK_DEV_REALM"] == "${NIP_KEYCLOAK_DEV_REALM:-false}"
    # the flag is only ever produced by the conditional, never written literally
    assert "&& echo --import-realm" in kc["command"][0]
    assert kc["command"][0].count("--import-realm") == 1

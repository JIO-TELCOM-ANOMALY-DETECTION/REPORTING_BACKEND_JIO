from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

RUN_DIRECTORY = Path(
    r"C:\Users\Aditya Pramod Pawar\JIO_Internship\ML_backend\runs"
    r"\run_20260908T150802683240Z_84c9ccf9"
)

BASE_URL = os.getenv(
    "REPORTING_BASE_URL",
    "http://127.0.0.1:8001",
).rstrip("/")

OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parent
    / "manual_smoke_test_outputs"
)

STAGE_URL_NAMES = {
    "part_a": "part-a",
    "part_b": "part-b",
    "part_c": "part-c",
    "part_d": "part-d",
}


# ============================================================
# HELPERS
# ============================================================

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Expected JSON object in {path}, "
            f"received {type(data).__name__}."
        )

    return data


def http_get_json(path: str) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"

    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            status_code = response.status
            raw_body = response.read().decode("utf-8")

    except HTTPError as error:
        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"HTTP {error.code} for {url}\n"
            f"{body}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            f"Could not connect to reporting backend at "
            f"{BASE_URL}.\n"
            f"Original error: {error}"
        ) from error

    try:
        payload = json.loads(raw_body)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Endpoint did not return valid JSON:\n"
            f"{url}\n\n"
            f"{raw_body[:1000]}"
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Expected JSON object from {url}; "
            f"received {type(payload).__name__}."
        )

    return status_code, payload


def save_response(name: str, payload: dict) -> Path:
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = OUTPUT_DIRECTORY / f"{name}.json"

    with destination.open(
        "w",
        encoding="utf-8",
    ) as file_handle:
        json.dump(
            payload,
            file_handle,
            indent=2,
            ensure_ascii=False,
        )

    return destination


def require_equal(
    actual,
    expected,
    description: str,
) -> None:
    if actual != expected:
        raise AssertionError(
            f"{description}: "
            f"expected {expected!r}, "
            f"received {actual!r}"
        )


def print_success(
    label: str,
    payload: dict,
    output_file: Path,
) -> None:
    print(f"[PASS] {label}")
    print(
        f"       keys = "
        f"{', '.join(payload.keys())}"
    )
    print(
        f"       saved = {output_file}"
    )


# ============================================================
# SOURCE IMMUTABILITY SNAPSHOT
# ============================================================

def collect_source_files(
    manifest: dict,
    run_directory: Path,
    attempt_id: str,
) -> list[Path]:
    protected_files: list[Path] = []

    manifest_path = run_directory / "manifest.json"

    if manifest_path.is_file():
        protected_files.append(manifest_path)

    attempt = manifest["attempts"][attempt_id]

    for stage_name in (
        "part_a",
        "part_b",
        "part_c",
        "part_d",
    ):
        stage = attempt["stages"][stage_name]

        execution_id = stage.get(
            "successful_execution_id"
        )

        if not execution_id:
            continue

        execution = (
            stage["executions"]
            [execution_id]
        )

        result_file = execution.get(
            "result_file"
        )

        if result_file:
            result_path = Path(result_file)

            if result_path.is_file():
                protected_files.append(
                    result_path
                )

    invocations = (
        manifest
        .get("inference", {})
        .get("invocations", {})
    )

    for invocation in invocations.values():
        result_file = invocation.get(
            "result_file"
        )

        if result_file:
            result_path = Path(result_file)

            if result_path.is_file():
                protected_files.append(
                    result_path
                )

    # De-duplicate while preserving order.
    return list(dict.fromkeys(protected_files))


def snapshot_hashes(
    files: list[Path],
) -> dict[Path, str]:
    return {
        file_path: sha256_file(file_path)
        for file_path in files
    }


# ============================================================
# MAIN TEST
# ============================================================

def main() -> int:
    print("=" * 70)
    print("REPORTING BACKEND — REAL RUN SMOKE TEST")
    print("=" * 70)

    if not RUN_DIRECTORY.is_dir():
        print(
            f"[FAIL] Run directory does not exist:\n"
            f"{RUN_DIRECTORY}"
        )
        return 1

    manifest_path = (
        RUN_DIRECTORY / "manifest.json"
    )

    if not manifest_path.is_file():
        print(
            f"[FAIL] manifest.json missing:\n"
            f"{manifest_path}"
        )
        return 1

    manifest = load_json(manifest_path)

    run_id = manifest["run_id"]

    attempt_id = manifest.get(
        "latest_attempt_id"
    )

    if not attempt_id:
        raise RuntimeError(
            "Manifest has no latest_attempt_id."
        )

    invocations = (
        manifest
        .get("inference", {})
        .get("invocations", {})
    )

    print(f"Run ID:     {run_id}")
    print(f"Attempt ID: {attempt_id}")
    print(
        f"Inference invocations: "
        f"{len(invocations)}"
    )
    print(f"Server: {BASE_URL}")
    print()

    # --------------------------------------------------------
    # Snapshot important source files before reporting reads.
    # --------------------------------------------------------

    protected_files = collect_source_files(
        manifest=manifest,
        run_directory=RUN_DIRECTORY,
        attempt_id=attempt_id,
    )

    before_hashes = snapshot_hashes(
        protected_files
    )

    print(
        f"Protected source files being "
        f"checked for mutation: "
        f"{len(protected_files)}"
    )
    print()

    # --------------------------------------------------------
    # 1. Health
    # --------------------------------------------------------

    status, payload = http_get_json(
        "/health"
    )

    require_equal(
        status,
        200,
        "Health HTTP status",
    )

    output = save_response(
        "00_health",
        payload,
    )

    print_success(
        "Health",
        payload,
        output,
    )

    # --------------------------------------------------------
    # 2. Run report
    # --------------------------------------------------------

    status, payload = http_get_json(
        f"/api/v1/reports/runs/{run_id}"
    )

    require_equal(
        status,
        200,
        "Run report HTTP status",
    )

    require_equal(
        payload.get("run_id"),
        run_id,
        "Run report run_id",
    )

    output = save_response(
        "01_run",
        payload,
    )

    print_success(
        "Run report",
        payload,
        output,
    )

    # --------------------------------------------------------
    # 3. Attempt report
    # --------------------------------------------------------

    status, payload = http_get_json(
        f"/api/v1/reports/runs/"
        f"{run_id}/attempts/{attempt_id}"
    )

    require_equal(
        status,
        200,
        "Attempt report HTTP status",
    )

    require_equal(
        payload.get("run_id"),
        run_id,
        "Attempt report run_id",
    )

    require_equal(
        payload.get("attempt_id"),
        attempt_id,
        "Attempt report attempt_id",
    )

    output = save_response(
        "02_attempt",
        payload,
    )

    print_success(
        "Attempt report",
        payload,
        output,
    )

    # --------------------------------------------------------
    # 4. A-D stage reports
    # --------------------------------------------------------

    for index, (
        manifest_stage,
        url_stage,
    ) in enumerate(
        STAGE_URL_NAMES.items(),
        start=3,
    ):
        stage_manifest = (
            manifest["attempts"]
            [attempt_id]
            ["stages"]
            [manifest_stage]
        )

        if (
            stage_manifest.get("status")
            != "completed"
        ):
            raise AssertionError(
                f"{manifest_stage} is not completed "
                f"in source manifest."
            )

        successful_execution_id = (
            stage_manifest.get(
                "successful_execution_id"
            )
        )

        if not successful_execution_id:
            raise AssertionError(
                f"{manifest_stage} has no "
                f"successful_execution_id."
            )

        endpoint = (
            f"/api/v1/reports/runs/"
            f"{run_id}/attempts/"
            f"{attempt_id}/stages/"
            f"{url_stage}"
        )

        status, payload = http_get_json(
            endpoint
        )

        require_equal(
            status,
            200,
            f"{manifest_stage} HTTP status",
        )

        require_equal(
            payload.get("run_id"),
            run_id,
            f"{manifest_stage} run_id",
        )

        require_equal(
            payload.get("attempt_id"),
            attempt_id,
            f"{manifest_stage} attempt_id",
        )

        output = save_response(
            f"{index:02d}_{manifest_stage}",
            payload,
        )

        print_success(
            manifest_stage,
            payload,
            output,
        )

    # --------------------------------------------------------
    # 5. Inference invocation listing
    # --------------------------------------------------------

    status, payload = http_get_json(
        f"/api/v1/reports/runs/"
        f"{run_id}/inference"
    )

    require_equal(
        status,
        200,
        "Inference list HTTP status",
    )

    output = save_response(
        "07_inference_list",
        payload,
    )

    print_success(
        "Inference invocation list",
        payload,
        output,
    )

    # --------------------------------------------------------
    # 6. Every inference invocation
    # --------------------------------------------------------

    if not invocations:
        raise AssertionError(
            "This run has no inference invocations."
        )

    for index, (
        invocation_id,
        invocation_manifest,
    ) in enumerate(
        invocations.items(),
        start=1,
    ):
        endpoint = (
            f"/api/v1/reports/runs/"
            f"{run_id}/inference/"
            f"{invocation_id}"
        )

        status, payload = http_get_json(
            endpoint
        )

        require_equal(
            status,
            200,
            "Inference detail HTTP status",
        )

        require_equal(
            payload.get("run_id"),
            run_id,
            "Inference report run_id",
        )

        require_equal(
            payload.get("invocation_id"),
            invocation_id,
            "Inference invocation_id",
        )

        expected_training_attempt = (
            invocation_manifest.get(
                "training_attempt_id"
            )
        )

        require_equal(
            payload.get(
                "training_attempt_id"
            ),
            expected_training_attempt,
            "Inference training_attempt_id",
        )

        output = save_response(
            f"08_inference_{index:02d}",
            payload,
        )

        print_success(
            f"Inference {invocation_id}",
            payload,
            output,
        )

    # --------------------------------------------------------
    # 7. Confirm ML backend source artifacts were untouched.
    # --------------------------------------------------------

    after_hashes = snapshot_hashes(
        protected_files
    )

    mutated_files = []

    for file_path, before_hash in (
        before_hashes.items()
    ):
        after_hash = after_hashes[file_path]

        if before_hash != after_hash:
            mutated_files.append(
                file_path
            )

    if mutated_files:
        print()
        print(
            "[FAIL] Reporting changed source "
            "ML-backend files:"
        )

        for file_path in mutated_files:
            print(f"       {file_path}")

        return 1

    print()
    print(
        "[PASS] Source immutability check"
    )
    print(
        "       Manifest/stage/inference "
        "result files were unchanged."
    )

    print()
    print("=" * 70)
    print("ALL REPORTING SMOKE TESTS PASSED")
    print("=" * 70)
    print()
    print(
        "Returned JSON responses were saved to:"
    )
    print(OUTPUT_DIRECTORY)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    except Exception as error:
        print()
        print("=" * 70)
        print("SMOKE TEST FAILED")
        print("=" * 70)
        print(
            f"{type(error).__name__}: {error}"
        )
        sys.exit(1)
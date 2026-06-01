#1 Contract Tests
Run uv run --group dev pytest -q tests/contract
Using CPython 3.12.13 interpreter at: /opt/hostedtoolcache/Python/3.12.13/x64/bin/python3.12
Creating virtual environment at: .venv
   Building wms @ file:///home/runner/work/WMS-Project/WMS-Project
Downloading zstandard (5.3MiB)
Downloading networkx (2.0MiB)
Downloading sqlalchemy (3.2MiB)
Downloading tokenizers (3.1MiB)
Downloading nvidia-cuda-runtime (2.1MiB)
Downloading kubernetes (1.9MiB)
Downloading torchvision (7.2MiB)
Downloading uvloop (4.2MiB)
Downloading hf-xet (4.0MiB)
Downloading nvidia-cusparse (139.2MiB)
Downloading nvidia-cufft (204.2MiB)
Downloading pandas (10.4MiB)
Downloading ruff (10.9MiB)
Downloading pillow (6.8MiB)
Downloading pyarrow (46.6MiB)
Downloading nvidia-nvshmem-cu13 (57.6MiB)
Downloading grpcio-tools (2.5MiB)
Downloading xformers (3.1MiB)
Downloading sympy (6.0MiB)
Downloading hf-transfer (3.4MiB)
Downloading scikit-learn (8.5MiB)
Downloading grpcio (6.5MiB)
Downloading nvidia-cuda-nvrtc (86.0MiB)
Downloading psycopg2-binary (4.1MiB)
Downloading nvidia-cublas (403.5MiB)
Downloading nvidia-cuda-cupti (10.2MiB)
Downloading torchao (3.1MiB)
Downloading torch (506.1MiB)
Downloading nvidia-curand (56.8MiB)
Downloading cryptography (4.3MiB)
Downloading triton (179.5MiB)
Downloading nvidia-nvjitlink (38.8MiB)
        repo = InMemoryPositionRepo()
        service = PositionService(repo)
    
        position = service.create_position(warehouse_id=1, code=" pick-01 ", type="picking")
    
>       assert position.code == "PICK-01"
               ^^^^^^^^^^^^^
E       AttributeError: 'coroutine' object has no attribute 'code'

tests/contract/test_warehouse_phase_g_contract.py:145: AttributeError
=============================== warnings summary ===============================
Services/reporting-service/src/app/shared/core/settings.py:48
  /home/runner/work/WMS-Project/WMS-Project/Services/reporting-service/src/app/shared/core/settings.py:48: UserWarning: Using default secret key! Set SECRET_KEY environment variable in production.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/contract/test_ai_phase_j_contract.py::test_ai_remains_opt_in_for_default_compose - KeyError: 'ai-service'
FAILED tests/contract/test_ai_phase_j_contract.py::test_ai_query_pipeline_routes_data_questions_through_template_boundary - ModuleNotFoundError: No module named 'ai_service'
FAILED tests/contract/test_async_analytics_contract.py::test_reporting_read_model_is_service_owned_and_idempotent - AssertionError: assert 'reporting_read_model_events' in 'services:\n  db:\n    image: postgres:16-alpine\n    environment:\n      POSTGRES_USER: ${POSTGRES_USER:-wms_user}\n ...nel --no-autoupdate --url http://api:8000\n    depends_on:\n      - api\n\nvolumes:\n  postgres_data:\n  redis_data:\n'
FAILED tests/contract/test_compose_data_ownership.py::test_default_compose_uses_service_owned_datastore_urls - KeyError: 'api-gateway'
FAILED tests/contract/test_compose_data_ownership.py::test_ai_profile_has_its_own_datastore_configuration - KeyError: 'ai-service'
FAILED tests/contract/test_event_bus_contract.py::test_compose_defines_redis_stream_event_bus - KeyError: 'event-bus'
FAILED tests/contract/test_internal_architecture_contract.py::test_application_layer_does_not_import_transport_runtime_clients - assert ["Services/id...core.redis']"] == []
  
  Left contains one more item: "Services/identity-service/src/app/modules/users/application/services/user_service.py imports forbidden modules: ['app.shared.core.redis']"
  
  Full diff:
  - []
  + [
  +     'Services/identity-service/src/app/modules/users/application/services/user_service.py '
  +     "imports forbidden modules: ['app.shared.core.redis']",
  + ]
FAILED tests/contract/test_internal_architecture_contract.py::test_compose_does_not_add_new_non_owned_init_tables_before_phase_b - KeyError: 'audit-service'
FAILED tests/contract/test_monolith_retirement_contract.py::test_monolith_is_not_in_active_uv_workspace - KeyError: 'uv'
FAILED tests/contract/test_monolith_retirement_contract.py::test_monolith_retirement_docs_define_archive_status_and_fixture_ownership - AssertionError: assert 'branch `Monolith`' in '# Warehouse Management System (WMS)\n\nA comprehensive, modern Warehouse Management System built with Python FastAPI,...unctionality\n5. Run the test suite\n6. Submit a pull request\n\n## 📝 License\n\n[Add your license information here]\n'
FAILED tests/contract/test_observability_contract.py::test_compose_is_otlp_ready - KeyError: 'api-gateway'
FAILED tests/contract/test_phase_l_migration_contract.py::test_runtime_table_bootstrap_is_local_only - KeyError: 'identity-service'
FAILED tests/contract/test_phase_q_cicd_contract.py::test_release_gates_workflow_blocks_drift_and_smoke_failures - assert 'Gateway contract and E2E smoke' in 'name: Release Gates\n\non:\n  pull_request:\n    branches:\n      - main\n  push:\n    branches:\n      - main\n  wor...>> $GITHUB_STEP_SUMMARY\n          echo "- Generate SBOM: ${{ needs.generate-sbom.result }}" >> $GITHUB_STEP_SUMMARY\n'
FAILED tests/contract/test_phase_q_cicd_contract.py::test_release_candidate_build_scan_and_ai_opt_in_are_enforced - assert 'release-candidate-build-scan' in 'name: Release Gates\n\non:\n  pull_request:\n    branches:\n      - main\n  push:\n    branches:\n      - main\n  wor...>> $GITHUB_STEP_SUMMARY\n          echo "- Generate SBOM: ${{ needs.generate-sbom.result }}" >> $GITHUB_STEP_SUMMARY\n'
FAILED tests/contract/test_resilience_contract.py::test_compose_exposes_resilience_configuration - KeyError: 'api-gateway'
FAILED tests/contract/test_security_contract.py::test_compose_exposes_security_configuration - KeyError: 'api-gateway'
FAILED tests/contract/test_warehouse_phase_g_contract.py::test_position_service_models_bins_without_inventory_quantities - AttributeError: 'coroutine' object has no attribute 'code'
17 failed, 100 passed, 1 warning in 5.06s
Error: Process completed with exit code 1.


#2 Quality gates
Run uv run --group dev pytest -q tests/contract
Using CPython 3.12.13 interpreter at: /opt/hostedtoolcache/Python/3.12.13/x64/bin/python3.12
Creating virtual environment at: .venv
   Building wms @ file:///home/runner/work/WMS-Project/WMS-Project
Downloading pillow (6.8MiB)
Downloading grpcio (6.5MiB)
Downloading sympy (6.0MiB)
Downloading networkx (2.0MiB)
Downloading ruff (10.9MiB)
Downloading uvloop (4.2MiB)
Downloading nvidia-cuda-runtime (2.1MiB)
Downloading kubernetes (1.9MiB)
Downloading torchvision (7.2MiB)
Downloading cuda-bindings (6.0MiB)
Downloading torchao (3.1MiB)
Downloading hf-xet (4.0MiB)
Downloading zstandard (5.3MiB)
Downloading pandas (10.4MiB)
Downloading nvidia-nvshmem-cu13 (57.6MiB)
Downloading nvidia-cudnn-cu13 (349.1MiB)
Downloading tokenizers (3.1MiB)
Downloading langchain-community (2.4MiB)
Downloading nvidia-cufft (204.2MiB)
Downloading pyarrow (46.6MiB)
Downloading nvidia-cusparse (139.2MiB)
Downloading faiss-cpu (22.7MiB)
Downloading chromadb (22.1MiB)
Downloading scipy (33.6MiB)
Downloading mypy (14.1MiB)
Downloading xformers (3.1MiB)
Downloading nvidia-curand (56.8MiB)
Downloading nvidia-cusparselt-cu13 (162.0MiB)
Downloading hf-transfer (3.4MiB)
Downloading nvidia-nccl-cu13 (187.4MiB)

    def test_position_service_models_bins_without_inventory_quantities() -> None:
        repo = InMemoryPositionRepo()
        service = PositionService(repo)
    
        position = service.create_position(warehouse_id=1, code=" pick-01 ", type="picking")
    
>       assert position.code == "PICK-01"
               ^^^^^^^^^^^^^
E       AttributeError: 'coroutine' object has no attribute 'code'

tests/contract/test_warehouse_phase_g_contract.py:145: AttributeError
=============================== warnings summary ===============================
Services/reporting-service/src/app/shared/core/settings.py:48
  /home/runner/work/WMS-Project/WMS-Project/Services/reporting-service/src/app/shared/core/settings.py:48: UserWarning: Using default secret key! Set SECRET_KEY environment variable in production.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/contract/test_ai_phase_j_contract.py::test_ai_remains_opt_in_for_default_compose - KeyError: 'ai-service'
FAILED tests/contract/test_ai_phase_j_contract.py::test_ai_query_pipeline_routes_data_questions_through_template_boundary - ModuleNotFoundError: No module named 'ai_service'
FAILED tests/contract/test_async_analytics_contract.py::test_reporting_read_model_is_service_owned_and_idempotent - AssertionError: assert 'reporting_read_model_events' in 'services:\n  db:\n    image: postgres:16-alpine\n    environment:\n      POSTGRES_USER: ${POSTGRES_USER:-wms_user}\n ...nel --no-autoupdate --url http://api:8000\n    depends_on:\n      - api\n\nvolumes:\n  postgres_data:\n  redis_data:\n'
FAILED tests/contract/test_compose_data_ownership.py::test_default_compose_uses_service_owned_datastore_urls - KeyError: 'api-gateway'
FAILED tests/contract/test_compose_data_ownership.py::test_ai_profile_has_its_own_datastore_configuration - KeyError: 'ai-service'
FAILED tests/contract/test_event_bus_contract.py::test_compose_defines_redis_stream_event_bus - KeyError: 'event-bus'
FAILED tests/contract/test_internal_architecture_contract.py::test_application_layer_does_not_import_transport_runtime_clients - assert ["Services/id...core.redis']"] == []
  
  Left contains one more item: "Services/identity-service/src/app/modules/users/application/services/user_service.py imports forbidden modules: ['app.shared.core.redis']"
  
  Full diff:
  - []
  + [
  +     'Services/identity-service/src/app/modules/users/application/services/user_service.py '
  +     "imports forbidden modules: ['app.shared.core.redis']",
  + ]
FAILED tests/contract/test_internal_architecture_contract.py::test_compose_does_not_add_new_non_owned_init_tables_before_phase_b - KeyError: 'audit-service'
FAILED tests/contract/test_monolith_retirement_contract.py::test_monolith_is_not_in_active_uv_workspace - KeyError: 'uv'
FAILED tests/contract/test_monolith_retirement_contract.py::test_monolith_retirement_docs_define_archive_status_and_fixture_ownership - AssertionError: assert 'branch `Monolith`' in '# Warehouse Management System (WMS)\n\nA comprehensive, modern Warehouse Management System built with Python FastAPI,...unctionality\n5. Run the test suite\n6. Submit a pull request\n\n## 📝 License\n\n[Add your license information here]\n'
FAILED tests/contract/test_observability_contract.py::test_compose_is_otlp_ready - KeyError: 'api-gateway'
FAILED tests/contract/test_phase_l_migration_contract.py::test_runtime_table_bootstrap_is_local_only - KeyError: 'identity-service'
FAILED tests/contract/test_phase_q_cicd_contract.py::test_release_gates_workflow_blocks_drift_and_smoke_failures - assert 'Gateway contract and E2E smoke' in 'name: Release Gates\n\non:\n  pull_request:\n    branches:\n      - main\n  push:\n    branches:\n      - main\n  wor...>> $GITHUB_STEP_SUMMARY\n          echo "- Generate SBOM: ${{ needs.generate-sbom.result }}" >> $GITHUB_STEP_SUMMARY\n'
FAILED tests/contract/test_phase_q_cicd_contract.py::test_release_candidate_build_scan_and_ai_opt_in_are_enforced - assert 'release-candidate-build-scan' in 'name: Release Gates\n\non:\n  pull_request:\n    branches:\n      - main\n  push:\n    branches:\n      - main\n  wor...>> $GITHUB_STEP_SUMMARY\n          echo "- Generate SBOM: ${{ needs.generate-sbom.result }}" >> $GITHUB_STEP_SUMMARY\n'
FAILED tests/contract/test_resilience_contract.py::test_compose_exposes_resilience_configuration - KeyError: 'api-gateway'
FAILED tests/contract/test_security_contract.py::test_compose_exposes_security_configuration - KeyError: 'api-gateway'
FAILED tests/contract/test_warehouse_phase_g_contract.py::test_position_service_models_bins_without_inventory_quantities - AttributeError: 'coroutine' object has no attribute 'code'
17 failed, 100 passed, 1 warning in 3.31s
Error: Process completed with exit code 1.
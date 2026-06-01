Now let me get the conftest and test files to understand the issue better:## Solution for Failing Job 78775833437

Root Causes:

The contract tests fail during collection with two distinct issues:

Missing shared_utils module - Multiple test files import from shared_utils which is not on the Python path:

tests/contract/test_event_bus_contract.py:7 - from shared_utils.events import EventEnvelope, build_event
tests/contract/test_event_contract_hardening.py:6 - from shared_utils.events import EventEnvelope, build_event
tests/contract/test_observability_contract.py:8 - from shared_utils.observability import ...
tests/contract/test_phase_m_event_delivery_contract.py:6 - from shared_utils.events import build_event
Missing DATABASE_URL environment variable - test_reporting_phase_f_contract.py fails with:

Code
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
database_url - Value error, DATABASE_URL environment variable is required
Solution:

1. Add shared_utils to Python path in conftest.py:
Add this to the path configuration section at the top of tests/conftest.py (after line 14):

Python
# Add src to Python path for all tests
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add shared_utils to Python path for contract tests
shared_utils_path = project_root / "shared_utils"
if shared_utils_path.exists() and str(shared_utils_path) not in sys.path:
    sys.path.insert(0, str(shared_utils_path))
2. Set DATABASE_URL environment variable in CI workflow:
Update .github/workflows/ci.yml (or release-gates.yml if contract tests run there) to set the required environment variable:

YAML
jobs:
  quality-gates:
    name: Quality Gates
    runs-on: ubuntu-latest
    env:
      DATABASE_URL: "sqlite:///test.db"  # Add this line
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Set up uv
        uses: astral-sh/setup-uv@v5
      - name: Contract tests
        if: github.event.inputs.skip_tests != 'true'
        env:
          TEST_DATABASE_URL: "sqlite:///test.db"  # Add this as well for consistency
        run: uv run --group dev pytest -q tests/contract
3. Alternative: Make settings validation optional in contract tests
If contract tests shouldn't require database configuration, update the Settings class to make database_url optional during testing:

Python
# In app/shared/core/settings.py or equivalent
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///test.db")  # Provide default instead of requiring it
    # ... rest of settings
Recommended Approach:

Implement both solutions 1 and 2:

Solution 1 ensures shared_utils is discovered during test collection
Solution 2 ensures the Settings class has required environment variables during CI runs
This will resolve all collection errors and allow the contract tests to proceed.

Solution for Failing Job 78775833408
Root Causes:

This job fails with identical issues to job 78775833437. The contract tests fail during collection with two distinct problems:

Missing shared_utils module - Multiple test files import from shared_utils which is not on the Python path:

tests/contract/test_event_bus_contract.py:7 - from shared_utils.events import EventEnvelope, build_event
tests/contract/test_event_contract_hardening.py:6 - from shared_utils.events import EventEnvelope, build_event
tests/contract/test_observability_contract.py:8 - from shared_utils.observability import ...
tests/contract/test_phase_m_event_delivery_contract.py:6 - from shared_utils.events import build_event
Missing DATABASE_URL environment variable - test_reporting_phase_f_contract.py fails during import with:

Code
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
database_url - Value error, DATABASE_URL environment variable is required
Solution:

1. Add shared_utils to Python path in tests/conftest.py:
Update the path configuration section (after line 14) to include the shared_utils directory:

Python
# Add src to Python path for all tests
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add shared_utils to Python path for contract tests
shared_utils_path = project_root / "shared_utils"
if shared_utils_path.exists() and str(shared_utils_path) not in sys.path:
    sys.path.insert(0, str(shared_utils_path))
2. Add DATABASE_URL environment variable to .github/workflows/release-gates.yml:
Update the quality-gates job to set the required environment variable (lines 30-45):

YAML
quality-gates:
  name: Quality Gates
  runs-on: ubuntu-latest
  env:
    DATABASE_URL: "sqlite:///test.db"  # Add this
  steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    - name: Set up uv
      uses: astral-sh/setup-uv@v5
    - name: Install kubectl
      uses: azure/setup-kubectl@v4
    - name: Contract tests
      if: github.event.inputs.skip_tests != 'true'
      env:
        TEST_DATABASE_URL: "sqlite:///test.db"  # Add this as well for consistency
      run: uv run --group dev pytest -q tests/contract
These changes will:

Allow pytest to discover and import from the shared_utils module during test collection
Provide the required DATABASE_URL environment variable so Settings can initialize without validation errors
Enable all contract tests to proceed past the collection phase
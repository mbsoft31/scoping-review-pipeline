"""Quick installation and testing script."""
import subprocess
import sys

def run_command(cmd, description):
    """Run a command and print output."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print('='*60)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"Return code: {result.returncode}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    """Run installation and testing."""

    # Step 1: Install package in editable mode
    if not run_command(
        f"{sys.executable} -m pip install -e .",
        "Step 1: Installing package in editable mode"
    ):
        print("❌ Failed to install package")
        return

    # Step 2: Install dev dependencies
    if not run_command(
        f"{sys.executable} -m pip install pytest pytest-cov pytest-asyncio black isort ruff respx faker hypothesis",
        "Step 2: Installing dev dependencies"
    ):
        print("⚠️  Some dev dependencies failed, but continuing...")

    # Step 3: Check if package can be imported
    print(f"\n{'='*60}")
    print("Step 3: Checking if srp can be imported")
    print('='*60)
    try:
        import srp
        print("✅ Successfully imported srp package")
        print(f"   Package location: {srp.__file__}")
    except ImportError as e:
        print(f"❌ Failed to import srp: {e}")
        return

    # Step 4: Run a simple test
    if not run_command(
        f"{sys.executable} -m pytest tests/unit/test_core_ids.py::TestNormalizeDOI::test_normalize_doi_standard -v",
        "Step 4: Running a simple test"
    ):
        print("⚠️  Test failed or pytest not available")

    # Step 5: Run all unit tests
    run_command(
        f"{sys.executable} -m pytest tests/unit -v --tb=short",
        "Step 5: Running all unit tests"
    )

    print(f"\n{'='*60}")
    print("Installation and testing complete!")
    print('='*60)

if __name__ == "__main__":
    main()


import os
import subprocess
import sys

def test_safe_flag_sets_config():
    # Use absolute path to ensure test works from any directory
    cli_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cli.py"))

    result = subprocess.run(
        [sys.executable, cli_path, "--safe"],
        capture_output=True,
        text=True
    )

    # Check that the CLI executed successfully
    assert result.returncode == 0, f"CLI failed with error:\n{result.stderr}"

    output = result.stdout.strip()

    # Use clear, specific assertions to make failure messages more helpful
    assert "batch_size=1" in output, "Expected 'batch_size=1' in CLI output"
    assert "precision=fp16" in output, "Expected 'precision=fp16' in CLI output"

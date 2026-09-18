# ComfyUI/tests/test_disk_quota_check.py

import shutil
import pytest
from unittest import mock
import builtins

def check_temp_disk_quota(min_free_gb=1):
    # Get the free disk space in bytes for the current directory
    free_bytes = shutil.disk_usage(".").free
    # Convert free bytes to gigabytes
    free_gb = free_bytes / (1024 ** 3)
    # If free space is less than the minimum required, print a message and exit
    if free_gb < min_free_gb:
        print("Not enough disk space")
        raise SystemExit(1)

def test_check_temp_disk_quota_triggers_exit_when_low():
    # Create a mocked disk usage result with only 0.4 GB free
    mocked_usage = shutil._ntuple_diskusage(total=100, used=99, free=int(0.4 * (1024**3)))

    # Patch shutil.disk_usage to return the mocked usage, and check that SystemExit is raised
    with mock.patch("shutil.disk_usage", return_value=mocked_usage), \
         pytest.raises(SystemExit) as excinfo:
        check_temp_disk_quota(min_free_gb=1)

    # Assert that the exit code is 1
    assert excinfo.value.code == 1

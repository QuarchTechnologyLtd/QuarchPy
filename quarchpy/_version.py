import os
import shutil
import glob
import logging

# Set up a logger for this package
logger = logging.getLogger(__name__)

__version__ = "2.2.15.dev2"

def _ensure_clean_qps_install():
    """
    Checks for a version-specific flag. If missing, it assumes a new install
    and wipes the 'connection_specific/qps' directory to remove legacy binaries.
    """
    package_dir = os.path.dirname(os.path.abspath(__file__))

    # The directory containing the binaries
    qps_dir = os.path.join(package_dir, "connection_specific", "QPS")

    # The flag file that indicates THIS version has been cleaned
    flag_file = os.path.join(package_dir, f".cleanup_done_{__version__}")

    # 2. CHECK: If the flag exists, do nothing.
    if os.path.exists(flag_file):
        return

    # 3. ACTION: Flag missing -> New Version Detected -> Wipe Folder
    logger.info(f"QuarchPy: New version {__version__} detected. Preparing environment...")

    if os.path.exists(qps_dir):
        try:
            logger.info(f"QuarchPy: Removing old QPS binaries from: {qps_dir}")
            shutil.rmtree(qps_dir) # Deletes folder and contents
            os.makedirs(qps_dir)   # Recreates the empty folder
            logger.info("QuarchPy: QPS directory successfully cleaned.")
        except OSError as e:
            logger.error(f"QuarchPy: Failed to remove old QPS folder. Error: {e}")
            logger.error("QuarchPy: Please manually delete the 'qps' folder to avoid binary conflicts.")
            # We return here so we don't write the flag, ensuring we try again next time
            return

    # 4. CLEANUP FLAGS: Remove flags from previous versions to keep root tidy
    # Matches .cleanup_done_2.1.0, .cleanup_done_2.0.0, etc.
    old_flags = glob.glob(os.path.join(package_dir, ".cleanup_done_*"))
    for f in old_flags:
        try:
            os.remove(f)
        except OSError:
            pass # Non-critical failure

    # 5. SET FLAG: Create the marker so we don't wipe again for this version
    try:
        with open(flag_file, 'w') as f:
            f.write("Cleanup completed.")
    except OSError:
        logger.warning(f"QuarchPy: Could not write cleanup flag to {flag_file}. Cleanup may run again on next import.")

# Run the check immediately when the package is imported
_ensure_clean_qps_install()
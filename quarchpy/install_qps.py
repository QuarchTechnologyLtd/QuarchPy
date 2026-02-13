import logging

logger = logging.getLogger(__name__)
import glob
import os
import sys
import zipfile
import requests
import shutil
import xml.etree.ElementTree as ET
from quarchpy.user_interface import printText, requestDialog
from quarchpy._version import __version__ as quarchpy_version

# --- Configuration ---
QPS_VERSION_FOR_DOWNLOAD = "1.50"
# URLs for the separate ZIP files.
QPS_DOWNLOAD_URL = f"https://quarch.com/software_update/qps/QPS_{QPS_VERSION_FOR_DOWNLOAD}.zip"
QPS_DOWNLOAD_URL_LATEST = "https://quarch.com/software_update/qps/QPS.zip"

# --- Path definitions using __file__ ---
try:
    current_file_path = os.path.abspath(__file__)
except NameError:
    # Fallback for interactive environments where __file__ is not defined.
    current_file_path = os.path.abspath(os.getcwd())

package_root = os.path.dirname(current_file_path)

TARGET_DIR = os.path.join(package_root, "connection_specific")
EXTRACTION_FOLDER_QPS = os.path.join(TARGET_DIR, "QPS")


def get_installed_qps_version(qps_folder):
    """Reads the appVersion from the app.properties file."""
    properties_file = os.path.join(qps_folder, "app.properties")
    if not os.path.exists(properties_file):
        return None  # File doesn't exist, can't determine version

    try:
        with open(properties_file, 'r') as f:
            for line in f:
                if line.strip().startswith("appVersion="):
                    # Split the line at '=' and return the version part
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        printText(f"  - Warning: Could not read version from {properties_file}. Error: {e}")
        return None  # Error reading file

    return None  # Version not found in the file


def _ensure_clean_qps_install():
    """
    Checks if QPS is present. If found (packaged with the wheel), we leave it alone.
    If missing, we perform a cleanup of the directory to ensure a clean state
    before any potential manual download.
    """
    package_dir = os.path.dirname(os.path.abspath(__file__))

    # Define paths
    qps_dir = os.path.join(package_dir, "connection_specific", "QPS")
    qps_jar = os.path.join(qps_dir, "qps.jar")

    # The flag file that indicates THIS version has been cleaned
    flag_file = os.path.join(package_dir, f".cleanup_done_{quarchpy_version}")

    # --- 1. NEW CHECK: Packaged Binary Detection ---
    # If qps.jar exists, we assume this is a bundled install (from your new workflow).
    # We do NOT want to delete it.
    if os.path.exists(qps_jar):
        logger.debug("QuarchPy: Found bundled QPS binaries. Skipping cleanup.")

        # We implicitly mark cleanup as done so we don't check this every import
        if not os.path.exists(flag_file):
            try:
                with open(flag_file, 'w') as f:
                    f.write("Cleanup skipped (Bundled binaries found).")
            except OSError:
                pass
        return

    # --- 2. CLEANUP LOGIC (Only runs if QPS is MISSING) ---
    # If we are here, QPS is missing. We verify if we've already cleaned up for this version.
    if os.path.exists(flag_file):
        return

    logger.info(f"QPS binaries missing and no flag found. Cleaning directories to prepare for installation.")

    # Clean QPS folder
    if os.path.exists(qps_dir):
        try:
            logger.info(f"QuarchPy: Removing old QPS binaries from: {qps_dir}")
            shutil.rmtree(qps_dir)
            os.makedirs(qps_dir)
            logger.info("QuarchPy: QPS directory successfully cleaned.")
        except OSError as e:
            logger.error(f"QuarchPy: Failed to clean QPS folder: {e}")

    # Remove old version flags
    old_flags = glob.glob(os.path.join(package_dir, ".cleanup_done_*"))
    for f in old_flags:
        try:
            os.remove(f)
        except OSError:
            pass

    # Create new flag
    try:
        with open(flag_file, 'w') as f:
            f.write("Cleanup completed (Clean install prepared).")
    except OSError:
        logger.warning(f"QuarchPy: Could not write cleanup flag to {flag_file}.")


def find_qps():
    """
    Checks for QPS. If missing or outdated, it attempts an
    online or offline installation. (JRE checks removed).
    """
    _ensure_clean_qps_install()

    qps_jar = "qps.jar"
    qps_path = os.path.join(EXTRACTION_FOLDER_QPS, qps_jar)

    # --- Component Verification ---
    qps_jar_exists = os.path.exists(qps_path)
    installed_qps_version = get_installed_qps_version(EXTRACTION_FOLDER_QPS)

    # --- Version Checking (Commented Out per request) ---
    # Check if the required version string starts with the installed version number.
    # This handles cases like required "1.48.1-SNAPSHOT" vs. installed "1.48".
    # qps_version_ok = False
    # if installed_qps_version:
    #     qps_version_ok = QPS_VERSION_FOR_DOWNLOAD.startswith(installed_qps_version)

    # We rely only on existence for now
    if qps_jar_exists:
        logger.info(f"QPS version {installed_qps_version} is correctly installed.")
        return True

    printText("--- Missing Component Detected ---")
    printText("Quarch Power Studio (QPS) is not installed.")

    # if not qps_version_ok:
    #     printText(f"QPS requires an update. (Installed: {installed_qps_version or 'Unknown'}, Required: {QPS_VERSION_FOR_DOWNLOAD})")

    # --- Installation Logic ---
    installation_successful = False
    response = ""
    if is_network_connection_available():
        network_available = True
        printText("\nAttempting online installation...")
        response = requestDialog("Would you like to download and install QPS? (y/n): ").lower()

        if response == 'y':
            qps_url_to_use = QPS_DOWNLOAD_URL

            if not is_download_url_valid(qps_url_to_use):
                printText(f"The download url {qps_url_to_use} is not valid.")
                printText(f"Defaulting to URL for the latest version of QPS: \n{QPS_DOWNLOAD_URL_LATEST}")

                latest_version = get_latest_qps_version()
                if latest_version != QPS_VERSION_FOR_DOWNLOAD:
                    printText(
                        f"Warning! The version of QuarchPy you are using does not officially support the latest version of QPS ({latest_version}).")
                    printText("Please consider upgrading QuarchPy.")
                    proceed = requestDialog(
                        "Would you like to proceed with downloading the latest version? (y/n): ").lower()

                    if proceed != 'y':
                        printText("Installation cancelled by user.")
                        qps_url_to_use = None
                    else:
                        qps_url_to_use = QPS_DOWNLOAD_URL_LATEST
                else:
                    qps_url_to_use = QPS_DOWNLOAD_URL_LATEST

            if not qps_url_to_use:
                # User cancelled
                installation_successful = False
            else:
                installation_successful = install_online(qps_url_to_use)
    else:
        printText("\nNo internet connection detected.")
        network_available = False

    if response == 'n' or not network_available:
        printText("To install manually, download the required file:")
        printText(f"  - QPS: {QPS_DOWNLOAD_URL} (or latest: {QPS_DOWNLOAD_URL_LATEST})")

        requestDialog("\nPress Enter to Continue after downloading.")
        response = requestDialog("Would you like to install from the manually downloaded ZIP file? (y/n) ").lower()
        if response == 'y':
            installation_successful = install_offline()

    if not installation_successful:
        printText("Installation was cancelled or failed.")
        return False

    # --- Final Check ---
    if not os.path.exists(qps_path):
        printText("\nInstallation failed. QPS is still missing.")
        printText("Please contact Quarch Support for further help: https://quarch.com/contact/")
        return False
    else:
        printText("\nQPS is now installed.")
        return True


def install_online(qps_url):
    """Handles online download and extraction of QPS."""
    qps_zip_path = os.path.join(TARGET_DIR, "QPS_download.zip")
    printText("\n--- Installing QPS ---")
    if download_file(qps_url, qps_zip_path):
        success = extract_and_move_qps(qps_zip_path)
        os.remove(qps_zip_path)
        printText(f"Cleaned up {qps_zip_path}")
        return success
    return False


def install_offline():
    """Prompts user for local ZIP file and installs QPS."""
    printText("\nPlease select the QPS ZIP file (e.g., QPS_1.47.zip).")
    qps_zip_filepath = prompt_for_zip_path("Select QPS ZIP File")
    if qps_zip_filepath:
        return extract_and_move_qps(qps_zip_filepath)
    return False  # User cancelled


def download_file(url, destination_path):
    """Downloads a file from a URL to a destination path with a progress bar."""
    try:
        printText(f"Downloading from {url}...")
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            with open(destination_path, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    done = int(50 * downloaded / total_size) if total_size > 0 else 0
                    sys.stdout.write(f"\r[{'=' * done}{' ' * (50 - done)}] {downloaded / (1024 * 1024):.2f} MB")
                    sys.stdout.flush()
        printText("\nDownload complete.")
        return True
    except requests.RequestException as e:
        printText(f"\nError: Failed to download file. {e}")
        return False


def extract_and_move_qps(zip_filepath):
    """Extracts QPS from its ZIP and moves it to ...quarchpy\\connection_specific\\QPS."""
    temp_extract_path = os.path.join(TARGET_DIR, "temp_extract_qps")
    printText(f"Processing QPS ZIP file: {os.path.basename(zip_filepath)}")
    try:
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)
        os.makedirs(temp_extract_path)
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_path)

        src_qps_folder = temp_extract_path
        if not os.path.exists(src_qps_folder):
            printText(f"  - Error: Extraction failed or folder structure unexpected.")
            return False

        # Handle case where QPS might be inside a subfolder in the zip
        if "qps" in os.listdir(src_qps_folder):
            src_qps_folder = os.path.join(src_qps_folder, "qps")

        os.makedirs(EXTRACTION_FOLDER_QPS, exist_ok=True)

        # Move contents
        for item in os.listdir(src_qps_folder):
            s = os.path.join(src_qps_folder, item)
            d = os.path.join(EXTRACTION_FOLDER_QPS, item)
            if os.path.isdir(s):
                if os.path.exists(d): shutil.rmtree(d)
                shutil.move(s, d)
            else:
                shutil.copy2(s, d)

        printText("QPS components moved successfully.")
        return True
    except (zipfile.BadZipFile, FileNotFoundError, OSError) as e:
        printText(f"\nError during QPS file operations: {e}")
        return False
    finally:
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)


def prompt_for_zip_path(title="Select ZIP File"):
    """Asks the user for the path to the zip file, trying a GUI first."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        printText("Opening file dialog...")
        root = tk.Tk()
        root.withdraw()
        filepath = filedialog.askopenfilename(
            title=title,
            filetypes=[("Zip files", "*.zip")]
        )
        return filepath
    except (ImportError, tk.TclError):
        printText("\nGUI not available. Please provide the path in the command line.")
        filepath = requestDialog(f"Enter the full path to the '{title}' ZIP file: ")
        if os.path.isfile(filepath):
            return filepath
        else:
            printText("Error: The provided path is not a valid file.")
            return None


def is_network_connection_available(timeout=5):
    """Checks for a reliable internet connection."""
    try:
        requests.head("https://www.quarch.com", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def get_latest_qps_version():
    """Fetches the latest QPS version number from the Quarch XML file."""
    version_xml_url = "https://quarch.com/software_update/qps/current_version_all.xml"
    try:
        printText(f"Checking for the latest QPS version from {version_xml_url}...")
        response = requests.get(version_xml_url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        latest_version_element = root.find('LatestVersion')

        if latest_version_element is not None:
            latest_version = latest_version_element.text
            printText(f"  - Latest version found: {latest_version}")
            return latest_version
        else:
            printText("  - Could not find 'LatestVersion' tag in the XML.")
    except (requests.RequestException, ET.ParseError) as e:
        printText(f"  - Error fetching or parsing version info: {e}")

    printText(f"  - Could not determine latest version. Falling back to {QPS_VERSION_FOR_DOWNLOAD}.")
    return QPS_VERSION_FOR_DOWNLOAD


def is_download_url_valid(url):
    """Checks if the provided URL is valid using a HEAD request."""
    try:
        printText(f"Checking URL: {url} ...")
        response = requests.head(url, timeout=10)
        response.raise_for_status()
        printText("  - URL is valid.")
        return True
    except requests.RequestException as e:
        printText(f"  - This URL is not valid: {e}")
        return False


if __name__ == "__main__":
    printText("--- Running Component Check ---")
    is_installed = find_qps()
    if is_installed:
        printText("\nSuccess! QPS is present.")
    else:
        printText("\n--- Script finished: QPS is missing. ---")
import os
import sys
import zipfile
import requests
import shutil
import xml.etree.ElementTree as ET

from quarchpy.user_interface import printText, requestDialog

# --- Configuration ---
QPS_VERSION_FOR_DOWNLOAD = "1.49"
# URLs for the separate ZIP files.
QPS_DOWNLOAD_URL = f"https://quarch.com/software_update/qps/QPS_{QPS_VERSION_FOR_DOWNLOAD}.zip"
JDK_JRE_DOWNLOAD_URL = "https://quarch.com/software_update/qps/jdk_jres.zip"
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
EXTRACTION_FOLDER_JDK_JRE = os.path.join(TARGET_DIR, "jdk_jres")


# --- NEW FUNCTION ---
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
        return None # Error reading file

    return None # Version not found in the file


# --- MODIFIED FUNCTION ---
def find_qps():
    """
    Checks for QPS and JDK/JRE. If any are missing or outdated, it attempts an
    online or offline installation of the required components.
    """
    qps_jar = "qps.jar"
    qps_path = os.path.join(EXTRACTION_FOLDER_QPS, qps_jar)

    # --- Cross-platform JDK/JRE check ---
    if sys.platform == "win32":
        jdk_folder_name = "win_amd64_jdk_jre"
        java_executable_name = "java.exe"
    elif sys.platform == "linux":
        jdk_folder_name = "lin_amd64_jdk_jre"
        java_executable_name = "java"
    elif sys.platform == "darwin":
        jdk_folder_name = "mac_amd64_jdk_jre"
        java_executable_name = "java"
    else:
        jdk_folder_name = None
        java_executable_name = None

    jdk_jre_check_file = None
    if jdk_folder_name:
        jdk_jre_check_file = os.path.join(EXTRACTION_FOLDER_JDK_JRE, jdk_folder_name, "bin", java_executable_name)

    # --- Component Verification ---
    qps_jar_exists = os.path.exists(qps_path)
    installed_qps_version = get_installed_qps_version(EXTRACTION_FOLDER_QPS)

    # Check if the required version string starts with the installed version number.
    # This handles cases like required "1.48.1-SNAPSHOT" vs. installed "1.48".
    qps_version_ok = False
    if installed_qps_version:
        qps_version_ok = QPS_VERSION_FOR_DOWNLOAD.startswith(installed_qps_version)

    qps_ok = qps_jar_exists and qps_version_ok
    jdk_found = jdk_jre_check_file and os.path.exists(jdk_jre_check_file)

    if qps_ok and jdk_found:
        printText(f"✅ QPS version {installed_qps_version} and JDK/JRE are correctly installed.")
        return True

    printText("--- Missing or Outdated Components Detected ---")
    qps_needed = not qps_ok
    jdk_jre_needed = not jdk_found

    if not qps_jar_exists:
        printText("Quarch Power Studio (QPS) is not installed.")
    elif not qps_version_ok:
        printText(f"QPS requires an update. (Installed: {installed_qps_version or 'Unknown'}, Required: {QPS_VERSION_FOR_DOWNLOAD})")

    if jdk_jre_needed:
        printText("Required Java JDK/JRE Binaries are not installed.")

    # --- Installation Logic ---
    installation_successful = False
    response = ""
    if is_network_connection_available():
        network_available = True
        printText("\nAttempting online installation...")
        response = requestDialog("Would you like to download and install the missing/outdated components? (y/n): ").lower()

        if response == 'y':
            qps_url_to_use = QPS_DOWNLOAD_URL

            if qps_needed and not is_download_url_valid(qps_url_to_use):
                printText(f"The download url {qps_url_to_use} is not valid.")
                printText(f"Defaulting to URL for the latest version of QPS: \n{QPS_DOWNLOAD_URL_LATEST}")

                latest_version = get_latest_qps_version()
                if latest_version != QPS_VERSION_FOR_DOWNLOAD:
                    printText(f"Warning! The version of QuarchPy you are using does not officially support the latest version of QPS ({latest_version}).")
                    printText("Please consider upgrading QuarchPy.")
                    proceed = requestDialog("Would you like to proceed with downloading the latest version? (y/n): ").lower()

                    if proceed != 'y':
                        printText("Installation cancelled by user.")
                        qps_url_to_use = None
                    else:
                        qps_url_to_use = QPS_DOWNLOAD_URL_LATEST
                else:
                    qps_url_to_use = QPS_DOWNLOAD_URL_LATEST

            if qps_needed and not qps_url_to_use:
                # User cancelled the download of a needed component
                installation_successful = False
            else:
                installation_successful = install_online(qps_url_to_use, JDK_JRE_DOWNLOAD_URL, qps_needed, jdk_jre_needed)
    else:
        printText("\nNo internet connection detected.")
        network_available = False

    if response == 'n' or not network_available:
        printText("To install manually, download the required files:")
        if qps_needed:
            printText(f"  - QPS: {QPS_DOWNLOAD_URL} (or latest: {QPS_DOWNLOAD_URL_LATEST})")
        if jdk_jre_needed:
            printText(f"  - JDK/JRE: {JDK_JRE_DOWNLOAD_URL}")

        requestDialog("\nPress Enter to Continue after downloading.")
        response = requestDialog("Would you like to install from the manually downloaded ZIP file(s)? (y/n) ").lower()
        if response == 'y':
            installation_successful = install_offline(qps_needed, jdk_jre_needed)

    if not installation_successful:
        printText("Installation was cancelled or failed.")
        return False

    # --- Final Check ---
    qps_found = os.path.exists(qps_path)
    jdk_found = jdk_jre_check_file and os.path.exists(jdk_jre_check_file)
    if (qps_needed and not qps_found) or (jdk_jre_needed and not jdk_found):
        printText("\nInstallation failed. Some components are still missing.")
        printText("Please contact Quarch Support for further help: https://quarch.com/contact/")
        return False
    else:
        printText("\nAll required components are now installed.")
        return True


def install_online(qps_url, jdk_jre_url, qps_needed, jdk_jre_needed):
    """Handles online download and extraction of required components."""
    qps_success = not qps_needed
    jdk_jre_success = not jdk_jre_needed

    if qps_needed:
        qps_zip_path = os.path.join(TARGET_DIR, "QPS_download.zip")
        printText("\n--- Installing QPS ---")
        if download_file(qps_url, qps_zip_path):
            qps_success = extract_and_move_qps(qps_zip_path)
            os.remove(qps_zip_path)
            printText(f"Cleaned up {qps_zip_path}")
        else:
            qps_success = False

    if jdk_jre_needed:
        jdk_jre_zip_path = os.path.join(TARGET_DIR, "jdk_jre.zip")
        printText("\n--- Installing JDK/JRE ---")
        if download_file(jdk_jre_url, jdk_jre_zip_path):
            jdk_jre_success = extract_and_move_jdk_jre(jdk_jre_zip_path)
            os.remove(jdk_jre_zip_path)
            printText(f"Cleaned up {jdk_jre_zip_path}")
        else:
            jdk_jre_success = False

    return qps_success and jdk_jre_success


def install_offline(qps_needed, jdk_jre_needed):
    """Prompts user for local ZIP files and installs them."""
    qps_success = not qps_needed
    jdk_jre_success = not jdk_jre_needed

    if qps_needed:
        printText("\nPlease select the QPS ZIP file (e.g., QPS_1.47.zip).")
        qps_zip_filepath = prompt_for_zip_path("Select QPS ZIP File")
        if qps_zip_filepath:
            qps_success = extract_and_move_qps(qps_zip_filepath)
        else:
            return False  # User cancelled

    if jdk_jre_needed:
        printText("\nPlease select the JDK/JRE ZIP file (jdk_jre.zip).")
        jdk_jre_zip_filepath = prompt_for_zip_path("Select JDK/JRE ZIP File")
        if jdk_jre_zip_filepath:
            jdk_jre_success = extract_and_move_jdk_jre(jdk_jre_zip_filepath)
        else:
            return False  # User cancelled

    return qps_success and jdk_jre_success


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
            printText(f"  - Error: 'qps' folder not found in the ZIP. Extraction failed.")
            return False

        os.makedirs(EXTRACTION_FOLDER_QPS, exist_ok=True)
        dest_qps_path = EXTRACTION_FOLDER_QPS
        if os.path.exists(dest_qps_path):
            printText(f"  - Removing old 'qps' folder...")
            shutil.rmtree(dest_qps_path)
        printText(f"  - Moving 'qps' to '{EXTRACTION_FOLDER_QPS}'...")
        shutil.move(os.path.join(src_qps_folder,"qps"), EXTRACTION_FOLDER_QPS)
        if os.path.exists(src_qps_folder):
            shutil.rmtree(src_qps_folder)
        printText("QPS components moved successfully.")
        return True
    except (zipfile.BadZipFile, FileNotFoundError, OSError) as e:
        printText(f"\nError during QPS file operations: {e}")
        return False
    finally:
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)


def extract_and_move_jdk_jre(zip_filepath):
    """Extracts JDK/JRE from its ZIP and moves all component folders."""
    temp_extract_path = os.path.join(TARGET_DIR, "temp_extract_jdk_jre")
    printText(f"Processing JDK/JRE ZIP file: {os.path.basename(zip_filepath)}")
    try:
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)
        os.makedirs(temp_extract_path)
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_path)

        os.makedirs(EXTRACTION_FOLDER_JDK_JRE, exist_ok=True)
        printText(f"  - Moving JDK/JRE contents to '{EXTRACTION_FOLDER_JDK_JRE}'...")
        for item_name in os.listdir(temp_extract_path):
            src_item = os.path.join(temp_extract_path, item_name)
            dest_item = os.path.join(EXTRACTION_FOLDER_JDK_JRE, item_name)
            if os.path.isdir(src_item):
                if os.path.exists(dest_item):
                    shutil.rmtree(dest_item)
                shutil.move(src_item, dest_item)
        printText("JDK/JRE components moved successfully.")
        return True
    except (zipfile.BadZipFile, FileNotFoundError, OSError) as e:
        printText(f"\nError during JDK/JRE file operations: {e}")
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
        printText("\nSuccess! All required components are present.")
    else:
        printText("\n--- Script finished: Not all components could be found or installed. ---")
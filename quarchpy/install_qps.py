import os
import sys
import zipfile
import requests

# --- Configuration ---
QPS_VERSION = "1.47"
# !!! IMPORTANT: Replace this with the actual URL to your ZIP file.
QPS_DOWNLOAD_URL = "https://quarch.com/software_update/qps/QPS.zip"  # Example URL
JDK_JRE_DOWNLOAD_URL = "https://quarch.com/software_update/qps/jdk_jres.zip"

# --- Path definitions using __file__ ---
# This gives the path to the current file (e.g., .../site-packages/quarchpy/install_qps.py)
current_file_path = os.path.abspath(__file__)

# This gives the path to the directory containing the current file (e.g., .../site-packages/quarchpy)
package_root = os.path.dirname(current_file_path)

# Now build the target paths from the package root
TARGET_DIR = os.path.join(package_root, "connection_specific")
EXTRACTION_FOLDER_QPS = os.path.join(TARGET_DIR, "QPS")
EXTRACTION_FOLDER_JDK_JRE = os.path.join(TARGET_DIR, "jdk_jres")


def find_qps():
    """
    Checks for the QPS jar and required JDK binaries. If anything is missing,
    it triggers the installation process.

    Returns:
        str: The full path to the jar file if all components are found or
             after a successful installation, otherwise None.
    """
    qps_jar = "qps.jar"
    qps_path = os.path.join(EXTRACTION_FOLDER_QPS, "win-amd64", qps_jar)
    # A representative file to check if JDK/JRE is extracted
    jdk_jre_check_file = os.path.join(EXTRACTION_FOLDER_JDK_JRE, "win_amd64_jdk_jre", "bin", "java.exe")

    qps_found = os.path.exists(qps_path)
    jdk_found = os.path.exists(jdk_jre_check_file)

    # --- If everything is already installed, we are done ---
    if qps_found and jdk_found:
        print(f"QPS found at: {qps_path}")
        print("Required Java JDK/JRE Binaries found.")
        return True

    # --- If something is missing, start the installation process ---
    print("--- Missing Components Detected ---")
    if not qps_found:
        print("Quarch Power Studio (QPS) is not installed.")
    if not jdk_found:
        print("Required Java JDK/JRE Binaries are not installed.")

    # Get user permission to install everything that's missing
    response = input("Would you like to download and install the missing components? (y/n): ").lower()
    if response != 'y':
        print("Installation cancelled by user.")
        return False

    # Ensure the base directory for downloads exists
    os.makedirs(TARGET_DIR, exist_ok=True)

    # Install QPS if it's missing
    if not qps_found:
        if not install_component("QPS", QPS_DOWNLOAD_URL, EXTRACTION_FOLDER_QPS):
             print("QPS installation failed. Aborting.")
             return False # Stop if a required component fails to install
        qps_found = os.path.exists(qps_path) # Re-check after install

    # Install JDK/JRE if it's missing
    if not jdk_found:
        if not install_component("jdk_jres", JDK_JRE_DOWNLOAD_URL, EXTRACTION_FOLDER_JDK_JRE):
            print("Java JDK/JRE installation failed. Aborting.")
            return False # Stop if a required component fails to install
        jdk_found = os.path.exists(jdk_jre_check_file) # Re-check after install

    # --- Final check after all installation attempts ---
    if qps_found and jdk_found:
        print("\nAll components are now installed.")
        return True
    else:
        print("\nInstallation failed. Some components are still missing.")
        return False


def install_component(name, url, extraction_folder):
    """
    Manages the download and extraction of a generic component zip file.

    Args:
        name (str): The display name of the component (e.g., "QPS").
        url (str): The URL to download the zip file from.
        extraction_folder (str): The folder to extract the contents to.

    Returns:
        bool: True if installation was successful, False otherwise.
    """
    print(f"--- Starting installation for {name} ---")
    if not is_network_connection_available():
        print(f"Error: No active internet connection. Cannot download {name}.")
        return False

    zip_filename = os.path.join(TARGET_DIR, f"{name}.zip")

    # Download the file
    try:
        print(f"Downloading {name} from {url}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            with open(zip_filename, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    done = int(50 * downloaded / total_size) if total_size > 0 else 0
                    sys.stdout.write(f"\r[{'=' * done}{' ' * (50 - done)}] {downloaded / (1024 * 1024):.2f} MB")
                    sys.stdout.flush()
        print("\nDownload complete.")
    except requests.RequestException as e:
        print(f"\nError: Failed to download {name}. {e}")
        return False

    # Extract the ZIP file and clean up
    try:
        print(f"Extracting '{zip_filename}' to '{extraction_folder}'...")
        os.makedirs(extraction_folder, exist_ok=True)
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(extraction_folder)
        print("Extraction successful.")
    except zipfile.BadZipFile:
        print(f"\nError: The downloaded file for {name} is corrupt.")
        return False
    finally:
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
            print(f"Cleaned up {zip_filename}.")

    return True


def is_network_connection_available(timeout=5):
    """Checks for a reliable internet connection."""
    try:
        requests.head("https://www.quarch.com", timeout=timeout)
        return True
    except requests.RequestException:
        return False
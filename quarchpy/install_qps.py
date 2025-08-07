import os
import sys
import zipfile
import requests
import shutil  # Import the shutil module for moving directories
import xml.etree.ElementTree as ET

# --- Configuration ---
QPS_VERSION = "1.47"
# The single URL for the combined ZIP file.
QPS_DOWNLOAD_URL = f"https://quarch.com/software_update/qps/QPS_{QPS_VERSION}.zip"
QPS_DOWNLOAD_URL_LATEST = "https://quarch.com/software_update/qps/QPS.zip"

# --- Path definitions using __file__ (as requested) ---
try:
    current_file_path = os.path.abspath(__file__)
except NameError:
    # __file__ is not defined when running in some interactive environments.
    # Fallback to the current working directory.
    current_file_path = os.path.abspath(os.getcwd())

package_root = os.path.dirname(current_file_path)

TARGET_DIR = os.path.join(package_root, "connection_specific")
EXTRACTION_FOLDER_QPS = os.path.join(TARGET_DIR, "QPS")
EXTRACTION_FOLDER_JDK_JRE = os.path.join(TARGET_DIR, "jdk_jres")


def find_qps():
    """
    Checks for QPS and JDK. If missing, it attempts an online or offline installation.
    """
    qps_jar = "qps.jar"
    qps_path = os.path.join(EXTRACTION_FOLDER_QPS, "win-amd64", qps_jar)

    # --- Cross-platform JDK/JRE check ---
    # Determine the correct subfolder and executable name based on the OS
    if sys.platform == "win32":
        jdk_folder_name = "win_amd64_jdk_jre"
        java_executable_name = "java.exe"
    elif sys.platform == "linux":
        jdk_folder_name = "lin_amd64_jdk_jre"
        java_executable_name = "java"
    elif sys.platform == "darwin":  # darwin is the value for macOS
        jdk_folder_name = "mac_amd64_jdk_jre"
        java_executable_name = "java"
    else:
        jdk_folder_name = None  # Unsupported OS
        java_executable_name = None

    # Construct the path to the java executable if the OS is supported
    if jdk_folder_name:
        jdk_jre_check_file = os.path.join(EXTRACTION_FOLDER_JDK_JRE, jdk_folder_name, "bin", java_executable_name)
    else:
        jdk_jre_check_file = None  # Path cannot be determined for unsupported OS

    qps_found = os.path.exists(qps_path)
    jdk_found = os.path.exists(jdk_jre_check_file)

    if qps_found and jdk_found:
        return True

    print("--- Missing Components Detected ---")
    if not qps_found:
        print("Quarch Power Studio (QPS) is not installed.")
    if not jdk_found:
        print("Required Java JDK/JRE Binaries are not installed.")

        # --- Installation Logic ---
    installation_successful = False
    if is_network_connection_available():
        print("\nAttempting online installation...")
        response = input("Would you like to download and install the missing components? (y/n): ").lower()

        if response == 'y':
            url_to_use = QPS_DOWNLOAD_URL
            version_to_use = QPS_VERSION

            # 1. Check if the primary URL is valid
            if not is_download_url_valid(url_to_use):
                print(f"The download url {url_to_use} is not valid.")
                print(f"Defaulting to URL for the latest version of QPS: \n{QPS_DOWNLOAD_URL_LATEST}")

                # 2. Check if the latest version is different and warn the user
                latest_version = get_latest_qps_version()
                if latest_version != QPS_VERSION:
                    print(f"Warning! The version of QuarchPy you are using does not officially support the latest version of QPS ({latest_version}).")
                    print("Please consider upgrading QuarchPy.")
                    proceed_response = input("Would you like to proceed with downloading the latest version? (y/n): ").lower()

                    # 3. If user cancels, stop the installation
                    if proceed_response != 'y':
                        print("Installation cancelled by user.")
                        # We set installation_successful to False and will skip the final install call
                        installation_successful = False
                        url_to_use = None  # Signal that we have no valid URL
                    else:
                        # User wants to proceed with the latest version
                        url_to_use = QPS_DOWNLOAD_URL_LATEST
                        version_to_use = "LATEST"
                else:
                    # The latest version is the same as the current, just use the latest URL
                    url_to_use = QPS_DOWNLOAD_URL_LATEST
                    version_to_use = "LATEST"

            # 4. Final installation call
            if url_to_use:
                # We only attempt installation if we have a valid URL to use
                installation_successful = install_online(url_to_use, version_to_use)
    else:
        print("\nNo internet connection detected.")
        # Provide the download URL for the user
        print("To install manually, please download the required file from:")
        print(f"  {QPS_DOWNLOAD_URL}")
        print("\n If the link above does not work please try the following link:")
        print(f"  {QPS_DOWNLOAD_URL_LATEST}")
        response = input("\nWould you like to locate a manually downloaded ZIP file to install from? (y/n): ").lower()
        if response == 'y':
            installation_successful = install_offline()

    if not installation_successful:
        print("Installation was cancelled or failed.")
        return False

    # --- Final Check ---
    qps_found = os.path.exists(qps_path)
    jdk_found = os.path.exists(jdk_jre_check_file)
    if qps_found and jdk_found:
        print("\nAll components are now installed.")
        return True
    else:
        print("\nInstallation failed. Some components are still missing.")
        return False


def install_online(url, qps_version):
    """Handles the online download and then calls the extraction function."""
    zip_filename = f"QPS_{qps_version}.zip"
    zip_filename_path = os.path.join(TARGET_DIR, zip_filename)
    try:
        print(f"Downloading components from {url}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            with open(zip_filename_path, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    done = int(50 * downloaded / total_size) if total_size > 0 else 0
                    sys.stdout.write(f"\r[{'=' * done}{' ' * (50 - done)}] {downloaded / (1024 * 1024):.2f} MB")
                    sys.stdout.flush()
        print("\nDownload complete.")
        # Call the core extraction logic
        return extract_and_move_components(zip_filename_path)
    except requests.RequestException as e:
        print(f"\nError: Failed to download components. {e}")
        return False
    finally:
        # Clean up the downloaded zip file after attempting extraction
        if os.path.exists(zip_filename_path):
            os.remove(zip_filename_path)
            print(f"Cleaned up downloaded file: {zip_filename_path}")


def install_offline():
    """Prompts user for a local zip file and calls the extraction function."""
    zip_filepath = prompt_for_zip_path()
    if not zip_filepath:
        return False
    return extract_and_move_components(zip_filepath)


def extract_and_move_components(zip_filepath):
    """
    Extracts a zip file to a temporary location, moves components to their
    final destinations, and cleans up the temporary folder.

    Args:
        zip_filepath (str): The full path to the source ZIP file.

    Returns:
        bool: True on success, False on failure.
    """
    temp_extract_path = os.path.join(TARGET_DIR, "temp_extract")
    print(f"\nProcessing ZIP file: {zip_filepath}")
    try:
        print(f"Extracting to temporary location: {temp_extract_path}...")
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)
        os.makedirs(temp_extract_path)
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_path)
        print("Temporary extraction successful.")

        src_qps_folder = os.path.join(temp_extract_path, 'win-amd64')
        src_jdk_folder = os.path.join(temp_extract_path, 'jdk_jres')

        os.makedirs(EXTRACTION_FOLDER_QPS, exist_ok=True)
        os.makedirs(EXTRACTION_FOLDER_JDK_JRE, exist_ok=True)

        # --- Overwrite logic for win-amd64 ---
        dest_qps_path = os.path.join(EXTRACTION_FOLDER_QPS, 'win-amd64')
        if os.path.exists(dest_qps_path):
            print(f"  - Existing 'win-amd64' folder found. Removing old version...")
            shutil.rmtree(dest_qps_path)
        print(f"Moving 'win-amd64' folder into '{EXTRACTION_FOLDER_QPS}'...")
        shutil.move(src_qps_folder, EXTRACTION_FOLDER_QPS)

        # --- Overwrite logic for jdk_jres contents ---
        print(f"Moving contents of 'jdk_jres' to '{EXTRACTION_FOLDER_JDK_JRE}'...")
        for item_name in os.listdir(src_jdk_folder):
            src_item = os.path.join(src_jdk_folder, item_name)
            dest_item = os.path.join(EXTRACTION_FOLDER_JDK_JRE, item_name)
            # If destination exists, remove it first to ensure overwrite
            if os.path.exists(dest_item):
                if os.path.isdir(dest_item):
                    shutil.rmtree(dest_item)
                else:
                    os.remove(dest_item)
            # Now move the new item
            shutil.move(src_item, dest_item)

        print("Components moved successfully.")
        return True
    except (zipfile.BadZipFile, FileNotFoundError, OSError) as e:
        print(f"\nError during file operations: {e}")
        return False
    finally:
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)
            print(f"Cleaned up temporary directory: {temp_extract_path}")


def prompt_for_zip_path():
    """
    Asks the user for the path to the zip file, trying a GUI first.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        print("Opening file dialog to select ZIP file...")
        root = tk.Tk()
        root.withdraw()  # Hide the main tkinter window
        filepath = filedialog.askopenfilename(
            title="Select QPS ZIP File",
            filetypes=[("Zip files", "*.zip")]
        )
        return filepath
    except (ImportError, tk.TclError):
        print("\nGUI not available. Please provide the path in the command line.")
        filepath = input("Enter the full path to the QPS ZIP file: ")
        if os.path.isfile(filepath):
            return filepath
        else:
            print("Error: The provided path is not a valid file.")
            return None


def is_network_connection_available(timeout=5):
    """Checks for a reliable internet connection."""
    try:
        requests.head("https://www.quarch.com", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def get_latest_qps_version():
    """
    Fetches the latest QPS version number from the Quarch XML file.

    Returns:
        str: The latest version number as a string, or the script's default
             QPS_VERSION on failure.
    """
    version_xml_url = "https://quarch.com/software_update/qps/current_version_all.xml"
    try:
        print(f"Checking for the latest QPS version from {version_xml_url}...")
        # Make a request to the URL, with a timeout for safety
        response = requests.get(version_xml_url, timeout=10)
        # Raise an exception for bad status codes (like 404 or 500)
        response.raise_for_status()

        # Parse the XML content from the response text
        root = ET.fromstring(response.text)

        # Find the 'LatestVersion' tag within the XML structure
        latest_version_element = root.find('LatestVersion')

        if latest_version_element is not None:
            # If the tag is found, return its text content
            latest_version = latest_version_element.text
            print(f"  - Latest version found: {latest_version}")
            return latest_version
        else:
            print("  - Could not find 'LatestVersion' tag in the XML.")

    except requests.RequestException as e:
        # Handle network errors (timeout, no connection, DNS error, etc.)
        print(f"  - Error fetching version info: {e}")
    except ET.ParseError as e:
        # Handle cases where the response is not valid XML
        print(f"  - Error parsing XML response: {e}")

    # If any step fails, fall back to the script's configured version
    print(f"  - Could not determine latest version. Falling back to {QPS_VERSION}.")
    return QPS_VERSION

def is_download_url_valid(url):
    """
    Checks if the provided URL is valid.

    Args:
        url (str): An URL.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        print(f"Checking URL: {url} ...")
        # Use a HEAD request to check the URL without downloading the content
        response = requests.head(url, timeout=10)
        # raise_for_status() will raise an exception for 4xx/5xx errors
        response.raise_for_status()
        print("  - URL is valid.")
        return True  # Return the valid URL and stop checking
    except requests.RequestException as e:
        print(f"  - This URL is not valid: {e}")

    return False  # Return None if no valid URLs were found


if __name__ == "__main__":
    print("--- Running Component Check ---")
    final_path = find_qps()
    if final_path:
        print(f"\nSuccess! Final QPS path: {final_path}")
    else:
        print("\n--- Script finished: Not all components could be found or installed. ---")

import os
import sys
import zipfile
import requests
import shutil  # Import the shutil module for moving directories

# --- Configuration ---
QPS_VERSION = "1.47"
# The single URL for the combined ZIP file.
QPS_DOWNLOAD_URL = f"https://quarch.com/software_update/qps/QPS_{QPS_VERSION}.zip"

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
            installation_successful = install_online()
    else:
        print("\nNo internet connection detected.")
        # Provide the download URL for the user
        print(f"To install manually, please download the required file from:")
        print(f"  {QPS_DOWNLOAD_URL}")
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


def install_online():
    """Handles the online download and then calls the extraction function."""
    zip_filename = os.path.join(TARGET_DIR, f"QPS_{QPS_VERSION}.zip")
    try:
        print(f"Downloading components from {QPS_DOWNLOAD_URL}...")
        with requests.get(QPS_DOWNLOAD_URL, stream=True) as r:
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
        # Call the core extraction logic
        return extract_and_move_components(zip_filename)
    except requests.RequestException as e:
        print(f"\nError: Failed to download components. {e}")
        return False
    finally:
        # Clean up the downloaded zip file after attempting extraction
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
            print(f"Cleaned up downloaded file: {zip_filename}")


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


if __name__ == "__main__":
    print("--- Running Component Check ---")
    final_path = find_qps()
    if final_path:
        print(f"\nSuccess! Final QPS path: {final_path}")
    else:
        print("\n--- Script finished: Not all components could be found or installed. ---")

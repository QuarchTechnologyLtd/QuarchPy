import os
import subprocess
import platform


def main():

    # Check the current OS
    current_os = platform.system()
    if current_os != "Windows":
        print("Fixing Permissions")
        # Check the current OS
        current_os = platform.system()
        # JRE 21 path
        java_path = os.path.dirname(os.path.abspath(__file__))
        java_path, junk = os.path.split(java_path)
        java_path = os.path.join(java_path, "jdk_j21_jres")
    
        # OS dependency
        if current_os in "Windows":
            java_path = java_path + "\\win_amd64_jdk_21_jre\\"
        elif current_os in "Linux":
            java_path = java_path + "/lin_amd64_jdk_21_jre/"
        elif current_os in "Darwin":
            java_path = java_path + "/mac_amd64_jdk_21_jre/"
        else:  # default to windows
            java_path = java_path + "\\win_amd64_jdk_21_jre\\"
    
        # Ensure the jres folder has the required permissions
        subprocess.call(['chmod', '-R', '+rwx', java_path])


def find_java_permissions():
    # Check the current OS
    current_os = platform.system()
    # JRE 21 path
    java_path = os.path.dirname(os.path.abspath(__file__))
    java_path, junk = os.path.split(java_path)
    java_path = os.path.join(java_path, "jdk_j21_jres")

    # OS dependency
    if current_os in "Windows":
        java_path = os.path.join(java_path, "win_amd64_jdk_21_jre","bin","java.exe")
    elif current_os in "Linux":
        java_path = java_path + "/lin_amd64_jdk_21_jre/bin/java"
    elif current_os in "Darwin":
        java_path = java_path + "/mac_amd64_jdk_21_jre/bin/java"
    else:  # default to windows
        java_path = java_path + "\\win_amd64_jdk_21_jre\\bin\\java"
    # Get the file status
    st = os.stat(java_path)
    # Extract the file permissions from the file status
    permissions = st.st_mode
    # Convert the file permissions to octal representation
    permissions_octal = oct(permissions)
    # Print the octal representation of the file permissions
    message=("Permissions of file at {}: {}".format(java_path, permissions_octal))

    execute_permissions = True
    if int(permissions_octal[-3]) % 2 ==0:
        execute_permissions = False
    if int(permissions_octal[-2]) % 2 ==0:
        execute_permissions = False
    if int(permissions_octal[-1]) % 2 ==0:
        execute_permissions = False

    return execute_permissions, message

if __name__ == "__main__":
    main()
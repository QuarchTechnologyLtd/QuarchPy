"""
Functions to allow automatic update and checking of the quarchpy package.
"""
from quarchpy import isQisRunning, closeQIS, isQpsRunning, closeQPS
import subprocess, sys
from quarchpy.user_interface import *


def main(argstring,auto_update=False):
    """
    Main function to allow access to access to the upgrade system from the command line
    
    """
    
    import argparse
    parser = argparse.ArgumentParser(description='Update Quarchpy parameters')
    parser.add_argument('-au', '--auto_update', help='If you definitely want to update', type=str.lower, default="n")
    parser.add_argument('-v', '--version', help='The version of quarchpy you would like to install',type=str)
    args = parser.parse_args(argstring)
    if args.auto_update in ('yes', 'true', 't', 'y', '1'):
        auto_update = True
    else:
        auto_update = False

    # Check if an update process is required
    if (check_if_update(auto_update)or args.version !=None):
        updateQuarchpy(args.version)


# TODO: Function name in wrong form, can we change this safely?
def updateQuarchpy(versionNumber=None):
    """
    Requests an upgrade to the quarchpy package_list. Prints to the terminal
    
    Parameters
    ----------
    versionNumber : str, optional
        Optional quarchpy version number in string form for previous/dev build access
        
    """
    
    printText("Updating Quarchpy")
    try:
        if versionNumber !=None:
            versionNumber = "=="+versionNumber
            printText((bytes(subprocess.check_output(['pip', 'install', 'quarchpy'+versionNumber], stderr=subprocess.STDOUT)).decode()))
        else:
            printText((bytes(subprocess.check_output(['pip', 'install', 'quarchpy', '--upgrade'], stderr=subprocess.STDOUT)).decode()))

        printText("Updated successfully")
    except Exception as e:
        printText("Could not upgrade quarchpy normally. Retrying with --user to install as global.")
        printText(e)
        try:
            if versionNumber !=None:
                printText((bytes(subprocess.check_output(['pip', 'install', 'quarchpy' + versionNumber, '--user'], stderr=subprocess.STDOUT)).decode()))
            else:
                printText((bytes(subprocess.check_output(['pip', 'install', 'quarchpy', '--upgrade', '--user'], stderr=subprocess.STDOUT)).decode()))
        except Exception as e:
            printText("Unable to update quarchpy. Contact support or run in cmd 'pip install quarchpy' ")
            printText(e)


# TODO: Wierd function to check for updates AND shutdown QIS/QPS but not actually do the update.
# Better form would be one function to check for update and one to 'prepare_for_update' by shutting things down
# (no prompt to user). This avoids so many low level user prompts and prints.
def check_if_update(auto_update):
    """
    Checks if updated version is available on pip. Prompts for shutdown of QIS and QPS if they are open, as this will
    prevent the update from working
    
    Parameters
    ----------
    auto_update : bool
        If True, QPS and QIS will be checked and shut down to prepare for update
    
    """
    # check if quarchpy is outdated
    # TOOO: No obvious version check code in here, how does this work?
    # TODO: Should this use the pkg_resources module from versionCompare?
    update_desired = False
    package_list = (bytes(subprocess.check_output(['pip', 'list', '-o'], stderr=subprocess.STDOUT)).decode())
    if "quarchpy" in package_list:
        printText("quarchpy is outdated")
        if auto_update:
            update_desired = True
        else:
            usr_input = requestDialog(title="", message="Do you want to update Y/N?")
            update_desired = True if usr_input == "Y" or usr_input == "y" else False

        if update_desired:
            if isQpsRunning() == True:
                 usr_input = requestDialog(title="", message="QPS must be closed to update. Close QPS Y/N?")
                 if usr_input == "Y" or usr_input == "y": closeQPS()
                 else: return False
            if isQisRunning() == True:
                 usr_input = requestDialog(title="", message="QIS must be closed to update. Close QIS Y/N?")
                 if usr_input == "Y" or usr_input == "y": closeQIS()
                 else: return False
        else:
            return False
    else:
        printText("quarchpy is up to date.")
        return False
    return True

# Allows flow through of command line arguments
if __name__ == "__main__":
    main(sys.argv[1:])
import os
import socket

def get_environment():
    """Returns 'HOME_PC' or 'WORK_PC' based on hostname"""
    hostname = socket.gethostname()
    if hostname == "DESKTOP-BRS4719":
        return "HOME_PC"
    else:
        return "WORK_PC"

def get_sudo_password():
    """Returns the appropriate sudo password for current environment"""
    env = get_environment()
    if env == "HOME_PC":
        return "Ne!sonB00ger"
    else:
        return "On Santa's Lap333"

def is_home_pc():
    return get_environment() == "HOME_PC"

def is_work_pc():
    return get_environment() == "WORK_PC"

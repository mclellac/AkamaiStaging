#!/usr/bin/env python

import argparse
import subprocess
import sys
import shutil
import platform
import os

# Package data for different OS and distributions
package_data = {
    "Linux": {
        "debian": {
            "manager": "apt-get",
            "update": ["update", "-y"],
            "options": ["install", "-y"],
            "packages": ["meson", "meson-python", "ninja-build", "libgtk-4-dev", "libadwaita-1-dev", "desktop-file-utils", "python3-dnspython", "python3-gi", "libglib2.0-dev"]
        },
        "ubuntu": "debian",  # Use the same config as Debian
        "fedora": {
            "manager": "dnf",
            "update": ["update", "-y"],
            "options": ["install", "-y"],
            "packages": ["meson", "python3-meson-python", "ninja-build", "gtk4-devel", "libadwaita-devel", "desktop-file-utils", "python3-dns", "python3-gobject", "glib2-devel"]
        },
        "centos": "fedora",
        "rhel": "fedora",
        "arch": {
            "manager": "pacman",
            "update": ["-Syu", "--noconfirm"],
            "options": ["-S", "--noconfirm"],
            "packages": ["meson", "meson-python", "ninja", "gtk4", "libadwaita", "desktop-file-utils", "python-dnspython", "python-gobject", "glib2"]
        },
    },
    "Darwin": {
        "manager": "brew",
        "update": ["update"],
        "options": ["install"],
        "packages": ["meson", "meson-python", "ninja", "gtk4", "libadwaita", "desktop-file-utils", "pygobject3", "glib"]
    }
}

def run_command(cmd):
    """Run a system command and handle errors."""
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(cmd)}:")
        if e.stderr:
            print(e.stderr)
        else:
            print("No detailed error message available.")
        sys.exit(1)

def install_packages(os_type, distro_id=None):
    """Install packages based on the OS type and distribution ID."""
    if os_type == "Darwin":
        data = package_data.get(os_type)
    else:
        data = package_data.get(os_type, {}).get(distro_id)

    if data is None:
        unsupported_msg = f">> Unsupported Linux distribution: {distro_id}" if distro_id else f"Unsupported OS type: {os_type}"
        print(unsupported_msg)
        sys.exit(1)

    manager = data["manager"]
    packages = data.get("packages", [])
    update = data.get("update", [])
    options = data.get("options", [])

    if os_type == "Linux" and os.geteuid() != 0:
        cmd_update = ["sudo"] + [manager] + update
        cmd_install = ["sudo"] + [manager] + options + packages
    else:
        cmd_update = [manager] + update
        cmd_install = [manager] + options + packages

    run_command(cmd_update)
    run_command(cmd_install)

    if os_type == "Darwin":
        print(">> pip installing pythondns as there is no Homebrew package.")
        run_command(["pip3", "install", "pythondns", "--break-system-packages"])


def check_and_delete_directory(directory):
    """Check if a directory exists and delete it if it does."""
    if os.path.exists(directory):
        print(f">> Removing existing directory: {directory}")
        subprocess.run(["sudo", "rm", "-rf", directory], check=True)


def build_application(os_type):
    """Build and install the application."""
    build_dir = "build"
    if os.path.exists(build_dir):
        print(f">> Existing build directory found. Removing {build_dir}...")
        shutil.rmtree(build_dir)
    run_command(["meson", "setup", build_dir])
    run_command(["ninja", "-C", build_dir, "--verbose"])
    run_command(["sudo", "ninja", "-C", build_dir, "install", "--verbose"])

    if os_type == "Darwin":
        print("\n>> This is a ridiculous workaround to Apple Inc breaking POSIX standards")
        print("with inane Python sandboxing.\n")
        python_version = platform.python_version()
        if python_version:
            # convert python_version X.X.X to pythonX.X to get the site-packages
            # directory.
            version_parts = python_version.split(".")
            python_version_str = "python" + version_parts[0] + "." + version_parts[1]
            old_path = f"/usr/local/usr/local/lib/{python_version_str}/site-packages/akstaging"
            new_path = f"/usr/local/lib/{python_version_str}/site-packages/"
            check_and_delete_directory(new_path + "akstaging")
            run_command(["sudo", "mv", "-v", old_path, new_path])
        else:
            print(">> Failed to determine Python version.")

def get_linux_distribution():
    """Retrieve the Linux distribution ID."""
    distro_id = ""
    if os.path.isfile("/etc/os-release"):
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    distro_id = line.strip().split("=")[1].lower()
                    break
    else:
        try:
            distro_id = subprocess.check_output(["lsb_release", "-is"]).decode().strip().lower()
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    return distro_id

def check_homebrew():
    """Check if Homebrew is installed on macOS."""
    if shutil.which("brew") is None:
        print(">> Homebrew not found. Please install it or install the dependencies manually.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Dependency installer and application builder")
    parser.add_argument("-i", "--install-deps", action="store_true", help="Install dependencies")
    parser.add_argument("-b", "--build", action="store_true", help="Build and install the application")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)

    os_type = platform.system()
    print(">> Detected OS Type:", os_type)

    if args.install_deps:
        message = f"""
-------------
 Disclaimer:
-------------
>> This script has been primarily tested on macOS and Fedora.
Package names or installation steps might need adjustments on
other Linux distributions. Please report any issues.
"""
        print(message)

        if os_type == "Linux":
            distro_id = get_linux_distribution()
            install_packages(os_type, distro_id)
        elif os_type == "Darwin":
            check_homebrew()
            install_packages(os_type)

        print("Dependencies installed successfully.")

    if args.build:
        build_application(os_type)
        print(">> Application built and installed successfully.")

if __name__ == "__main__":
    main()



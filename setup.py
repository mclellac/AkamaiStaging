#!/usr/bin/env python3

import argparse
import subprocess
import sys
import shutil
import platform
import os
from pathlib import Path

package_data = {
    "Linux": {
        "debian": {
            "manager": "apt-get",
            "update": ["update", "-y"],
            "options": ["install", "-y"],
            "packages": ["meson", "meson-python", "ninja-build", "libgtk-4-dev", "libadwaita-1-dev", "desktop-file-utils", "python3-dnspython", "python3-gi", "libglib2.0-dev"]
        },
        "ubuntu": "debian",  
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
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: Command {' '.join(cmd)} failed.")
        print(e.stderr)
        sys.exit(1)

def install_packages(os_type, distro_id=None):
    """Install packages based on the OS type and distribution ID."""
    data = package_data.get(os_type, {}).get(distro_id)
    if data is None:
        print(f"Unsupported OS/distribution: {os_type}/{distro_id}")
        sys.exit(1)

    manager = data["manager"]
    packages = data.get("packages", [])
    update = data.get("update", [])
    options = data.get("options", [])

    if os_type == "Linux" and os.geteuid() != 0:
        cmd = ["sudo"] + [manager] + update + options + packages
    else:
        cmd = [manager] + update + options + packages

    run_command(cmd)

    if os_type == "Darwin":
        run_command(["pip3", "install", "pythondns", "--break-system-packages"])

def check_and_delete_directory(directory):
    """Check if a directory exists and delete it if it does, with user message."""
    if os.path.exists(directory):
        print(f"[Cleanup] Removing existing directory: {directory}")
        subprocess.run(["sudo", "rm", "-rf", directory], check=True)

def build_application(os_type):
    """Build and install the application with informative messages."""
    build_dir = Path("build")
    check_and_delete_directory(build_dir)

    print("\n[Build] Configuring project with Meson...")
    run_command(["meson", "setup", build_dir])
    
    print("[Build] Compiling with Ninja...")
    run_command(["ninja", "-C", build_dir])

    if os_type == "Linux" and os.geteuid() != 0:
        run_command(["sudo", "ninja", "-C", build_dir, "install"])
    else:
        run_command(["ninja", "-C", build_dir, "install"])

    print("[Build] Installation complete!")
    
    if os_type == "Darwin":
        # Get the first site-packages directory in sys.path
        site_packages_dir = next((p for p in sys.path if "site-packages" in p), None)
        if site_packages_dir:
            old_path = Path(site_packages_dir) / "akstaging"
            new_path = Path(site_packages_dir)
            
            if old_path.exists():
                print("\n[macOS Fix] Moving akstaging to correct site-packages location...")
                shutil.move(str(old_path), str(new_path))
            else:
                print("\n[macOS Fix] Not needed: akstaging not found in expected location.")
        else:
            print(">> Failed to determine Python site-packages directory.")

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
    print(f"[System] Detected operating system: {os_type}")

    if args.install_deps:
        print("\n--- Installing Dependencies ---") 
        if os_type == "Linux":
            distro_id = get_linux_distribution()
            print(f"[System] Linux distribution: {distro_id}")
            install_packages(os_type, distro_id)
        elif os_type == "Darwin":
            check_homebrew()
            install_packages(os_type)

        print("\n[Success] Dependencies installed successfully!\n")

    if args.build:
        print("\n--- Building Application ---")
        build_application(os_type)


if __name__ == "__main__":
    main()


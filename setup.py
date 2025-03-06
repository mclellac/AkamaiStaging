#!/usr/bin/env python3

import argparse
import subprocess
import sys
import shutil
import platform
import os
from pathlib import Path

distros = {
    "debian": "debian",
    "ubuntu": "debian",  # Use the same config as Debian
    "linuxmint": "debian",
    "kali": "debian",
    "fedora": "fedora",
    "centos": "fedora",
    "rhel": "fedora",
    "arch": "arch",
    "darwin": "darwin",
}

# Package data for different OS and distributions
package_data = {
    "Linux": {
        "debian": {
            "manager": "apt",
            "update": ["update", "-y"],
            "options": ["install", "-y"],
            "packages": [
                "meson",
                "python3-mesonpy",
                "ninja-build",
                "libgtk-4-dev",
                "libadwaita-1-dev",
                "desktop-file-utils",
                "python3-dnspython",
                "python3-gi",
                "libglib2.0-dev",
                "python-gi-dev",
                "gettext",
            ],
        },
        "fedora": {
            "manager": "dnf",
            "update": ["update", "-y"],
            "options": ["install", "-y"],
            "packages": [
                "meson",
                "python3-meson-python",
                "ninja-build",
                "gtk4-devel",
                "libadwaita-devel",
                "desktop-file-utils",
                "python3-dns",
                "python3-gobject",
                "glib2-devel",
                "cmake",
                "python3-gobject-devel",
                "gettext",
            ],
        },
        "arch": {
            "manager": "pacman",
            "update": ["-Syu", "--noconfirm"],
            "options": ["-S", "--noconfirm"],
            "packages": [
                "meson",
                "meson-python",
                "ninja",
                "gtk4",
                "libadwaita",
                "desktop-file-utils",
                "python-dnspython",
                "python-gobject",
                "glib2",
            ],
        },
    },
    "Darwin": {
        "darwin": {  # Adjusted the structure to match how other OSes are defined
            "manager": "brew",
            "update": ["upgrade"],
            "options": ["install"],
            "packages": [
                "meson",
                "meson-python",
                "ninja",
                "gtk4",
                "libadwaita",
                "desktop-file-utils",
                "pygobject3",
                "glib",
            ],
        }
    },
}


def run_command(cmd):
    """Run a system command and handle errors."""
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(
            f"Error: Command {' '.join(map(str, cmd))} failed."
        )  # Convert PosixPath to str
        print(e.stderr)
        sys.exit(1)


def detect_os_and_distro():
    os_type = platform.system()
    if os_type == "Linux":
        try:
            with open("/etc/os-release") as f:
                lines = f.readlines()
                distro_info = {}
                for line in lines:
                    key, value = line.strip().split("=")
                    distro_info[key] = value.strip('"')
                distro = distro_info.get("ID", "unknown")
        except Exception as e:
            raise RuntimeError(f"Could not determine Linux distribution: {str(e)}")
    elif os_type == "Darwin":
        distro = "darwin"
    else:
        raise ValueError(f"Unsupported operating system: {os_type}")

    return os_type, distro


def install_packages():
    os_type, distro = detect_os_and_distro()
    distro_key = distros.get(distro, None)  # Map distro to its config key

    if os_type in package_data and distro_key in package_data[os_type]:
        data = package_data[os_type][distro_key]
        manager = data["manager"]
        update_cmd = [manager] + data["update"]
        install_cmd = [manager] + data["options"] + data["packages"]

        if os_type == "Linux" and os.geteuid():
            update_cmd.insert(0, "sudo")
            install_cmd.insert(0, "sudo")

        # Running the commands
        print("Running command:", " ".join(update_cmd))
        run_command(update_cmd)
        print("Running command:", " ".join(install_cmd))
        run_command(install_cmd)
    else:
        raise ValueError(f"Unsupported OS or distribution: {os_type}, {distro}")


def check_and_delete_directory(directory):
    """Check if a directory exists and delete it if it does, with user message."""
    if os.path.exists(directory):
        print(f"[Cleanup] Removing existing directory: {directory}")
        run_command(["sudo", "rm", "-rf", directory])


def build_application(os_type):
    """Build and install the application with informative messages."""
    build_dir = Path("build")
    check_and_delete_directory(build_dir)

    print("\n[Build] Configuring project with Meson...")
    run_command(["meson", "setup", str(build_dir)])  # Convert PosixPath to str

    print("[Build] Compiling with Ninja...")
    run_command(["ninja", "-C", str(build_dir)])  # Convert PosixPath to str
    print("[Build] Installing with Ninja...")
    run_command(["sudo", "ninja", "-C", str(build_dir), "install"])

    print("[Build] Installation complete!")

    if os_type == "Darwin":
        # Get the first site-packages directory in sys.path
        site_packages_dir = next((p for p in sys.path if "site-packages" in p), None)
        if site_packages_dir:
            old_path = Path("/usr/local" + site_packages_dir) / "akstaging"
            new_path = Path(site_packages_dir) / "akstaging"

            if new_path.exists():
                print(f"[macOS Fix] Removing old directory: {new_path}")
                run_command(["sudo", "rm", "-rf", str(new_path)])

            if old_path.exists():
                print(
                    "[macOS Fix] Moving akstaging to correct site-packages location..."
                )
                run_command(["sudo", "mv", "-v", str(old_path), str(new_path)])
        else:
            print(">> Failed to determine Python site-packages directory.")


def check_homebrew():
    """Check if Homebrew is installed on macOS."""
    if shutil.which("brew") is None:
        print(
            ">> Homebrew not found. Please install it or install the dependencies manually."
        )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Dependency installer and application builder"
    )
    parser.add_argument(
        "-i", "--install-deps", action="store_true", help="Install dependencies"
    )
    parser.add_argument(
        "-b", "--build", action="store_true", help="Build and install the application"
    )
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)

    os_type, distro = detect_os_and_distro()
    print(f"[System] Detected operating system: {os_type}")
    print(f"[System] Detected distribution: {distro}")

    if args.install_deps:
        print("\n--- Installing Dependencies ---")
        if os_type == "Darwin":
            check_homebrew()
        install_packages()

        print("\n[Success] Dependencies installed successfully!\n")

    if args.build:
        print("\n--- Building Application ---")
        build_application(os_type)


if __name__ == "__main__":
    main()

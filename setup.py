#!/usr/bin/env python3

import argparse
import os
import platform
import shutil
import subprocess
import sys
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
    "archarm": "arch",
    "darwin": "darwin",
}

# Package data for different OS and distributions
package_data: dict[str, dict[str, dict[str, str | list[str]]]] = {
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


def ensure_macos_homebrew_path() -> None:
    """Ensure Homebrew binary paths are included in PATH on macOS."""
    if platform.system() == "Darwin":
        brew_paths = [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
        ]
        current_path = os.environ.get("PATH", "")
        path_list = current_path.split(os.pathsep) if current_path else []
        for p in brew_paths:
            if os.path.isdir(p) and p not in path_list:
                path_list.insert(0, p)
        os.environ["PATH"] = os.pathsep.join(path_list)


def find_executable(cmd_name: str) -> str:
    """Finds an executable in PATH or standard macOS Homebrew locations."""
    ensure_macos_homebrew_path()
    path = shutil.which(cmd_name)
    if path:
        return path
    if platform.system() == "Darwin":
        for brew_dir in ["/opt/homebrew/bin", "/usr/local/bin"]:
            candidate = os.path.join(brew_dir, cmd_name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return cmd_name


def run_command(cmd: list[str]) -> None:
    """Run a system command and handle errors."""
    if not cmd:
        return
    resolved_cmd = [str(arg) for arg in cmd]
    if resolved_cmd[0] == "sudo" and len(resolved_cmd) > 1:
        resolved_cmd[1] = find_executable(resolved_cmd[1])
    else:
        resolved_cmd[0] = find_executable(resolved_cmd[0])

    try:
        result = subprocess.run(resolved_cmd, check=True, text=True, capture_output=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: Command {' '.join(map(str, cmd))} failed.")  # Convert PosixPath to str
        print(e.stderr)
        sys.exit(1)


def detect_os_and_distro() -> tuple[str, str]:
    os_type = platform.system()
    if os_type == "Linux":
        try:
            with open("/etc/os-release") as f:
                lines = f.readlines()
                distro_info: dict[str, str] = {}
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        distro_info[key.strip()] = value.strip().strip("\"'")
                distro = distro_info.get("ID", "unknown")
                if distro not in distros and "ID_LIKE" in distro_info:
                    for like_id in distro_info["ID_LIKE"].split():
                        if like_id in distros:
                            distro = like_id
                            break
        except Exception as e:
            raise RuntimeError(f"Could not determine Linux distribution: {str(e)}") from e
    elif os_type == "Darwin":
        distro = "darwin"
    else:
        raise ValueError(f"Unsupported operating system: {os_type}")

    return os_type, distro


def install_packages() -> None:
    os_type, distro = detect_os_and_distro()
    distro_key = distros.get(distro, None)  # Map distro to its config key

    if os_type in package_data and distro_key and distro_key in package_data[os_type]:
        data = package_data[os_type][distro_key]
        manager = str(data["manager"])
        update_opts = data["update"] if isinstance(data["update"], list) else [str(data["update"])]
        options_opts = data["options"] if isinstance(data["options"], list) else [str(data["options"])]
        packages_opts = data["packages"] if isinstance(data["packages"], list) else [str(data["packages"])]

        update_cmd: list[str] = [manager] + update_opts
        install_cmd: list[str] = [manager] + options_opts + packages_opts

        if os_type == "Linux" and hasattr(os, "geteuid") and os.geteuid() != 0:
            update_cmd.insert(0, "sudo")
            install_cmd.insert(0, "sudo")

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
        py_version_major = sys.version_info.major
        py_version_minor = sys.version_info.minor

        incorrectly_installed_path = Path(
            f"/usr/local/usr/local/lib/python{py_version_major}.{py_version_minor}/site-packages/akstaging"
        )
        correct_install_path = Path(
            f"/usr/local/lib/python{py_version_major}.{py_version_minor}/site-packages/akstaging"
        )

        if correct_install_path.exists():
            print(f"[macOS Fix] Removing existing directory at correct location (if any): {correct_install_path}")
            run_command(["sudo", "rm", "-rf", str(correct_install_path)])

        if incorrectly_installed_path.exists():
            print(f"[macOS Fix] Moving 'akstaging' from '{incorrectly_installed_path}' to '{correct_install_path}'...")
            run_command(["sudo", "mkdir", "-p", str(correct_install_path.parent)])
            run_command(["sudo", "mv", "-v", str(incorrectly_installed_path), str(correct_install_path)])
        else:
            print(f"[macOS Fix] Source directory '{incorrectly_installed_path}' not found. Cannot apply fix.")


def check_homebrew() -> None:
    """Check if Homebrew is installed on macOS."""
    brew_path = find_executable("brew")
    if not os.path.isfile(brew_path) or not os.access(brew_path, os.X_OK):
        print(">> Homebrew not found. Please install it or install the dependencies manually.")
        sys.exit(1)


def main():
    ensure_macos_homebrew_path()
    parser = argparse.ArgumentParser(description="Dependency installer and application builder")
    parser.add_argument("-i", "--install-deps", action="store_true", help="Install dependencies")
    parser.add_argument("-b", "--build", action="store_true", help="Build and install the application")
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

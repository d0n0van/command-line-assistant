"""Platform detection for command-line-assistant."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
from enum import Enum


class PlatformType(Enum):
    """Supported platform types."""
    RHEL = "rhel"  # RHEL, CentOS, Fedora, Rocky, AlmaLinux
    DEBIAN = "debian"  # Debian, Ubuntu
    ARCH = "arch"  # Arch Linux, Manjaro
    SUSE = "suse"  # openSUSE, SUSE Linux Enterprise
    GENTOO = "gentoo"  # Gentoo
    UNKNOWN = "unknown"


class PlatformDetector:
    """Detects the Linux distribution and provides platform-specific information."""

    # Platform-specific command mappings
    PLATFORM_COMMANDS = {
        PlatformType.RHEL: {
            "package_manager": "dnf",
            "service_manager": "systemctl",
            "firewall": "firewalld",
            "network": "nmcli",
            "alternatives": ["yum", "dnf"],  # Fallback order
        },
        PlatformType.DEBIAN: {
            "package_manager": "apt",
            "service_manager": "systemctl",
            "firewall": "ufw",
            "network": "nmcli",
            "alternatives": ["apt-get", "apt"],
        },
        PlatformType.ARCH: {
            "package_manager": "pacman",
            "service_manager": "systemctl",
            "firewall": "ufw",
            "network": "nmcli",
            "alternatives": ["pacman"],
        },
        PlatformType.SUSE: {
            "package_manager": "zypper",
            "service_manager": "systemctl",
            "firewall": "firewalld",
            "network": "nmcli",
            "alternatives": ["zypper"],
        },
        PlatformType.GENTOO: {
            "package_manager": "emerge",
            "service_manager": "systemctl",
            "firewall": "ufw",
            "network": "nmcli",
            "alternatives": ["emerge"],
        },
    }

    def __init__(self):
        """Initialize platform detector."""
        self._platform: Optional[PlatformType] = None
        self._distribution: Optional[str] = None
        self._version: Optional[str] = None
        self._detection_reason: Optional[str] = None
        self._detect_platform()

    def _detect_platform(self) -> None:
        """Detect the Linux platform."""
        # Method 1: Check /etc/os-release (most reliable)
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            try:
                with open(os_release_path, 'r') as f:
                    os_release = {}
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            # Remove quotes from value
                            value = value.strip('"').strip("'")
                            os_release[key] = value

                self._distribution = os_release.get('NAME', 'Unknown')
                self._version = os_release.get('VERSION_ID', 'Unknown')
                id_like = os_release.get('ID_LIKE', '').lower()
                distro_id = os_release.get('ID', '').lower()

                # Determine platform type
                if distro_id in ['rhel', 'centos', 'fedora', 'rocky', 'almalinux', 'ol']:
                    self._platform = PlatformType.RHEL
                    self._detection_reason = f"Detected via /etc/os-release: ID={distro_id}, ID_LIKE={id_like}"
                elif distro_id in ['debian', 'ubuntu', 'raspbian']:
                    self._platform = PlatformType.DEBIAN
                    self._detection_reason = f"Detected via /etc/os-release: ID={distro_id}, ID_LIKE={id_like}"
                elif distro_id in ['arch', 'manjaro']:
                    self._platform = PlatformType.ARCH
                    self._detection_reason = f"Detected via /etc/os-release: ID={distro_id}, ID_LIKE={id_like}"
                elif distro_id in ['opensuse', 'sles', 'suse']:
                    self._platform = PlatformType.SUSE
                    self._detection_reason = f"Detected via /etc/os-release: ID={distro_id}, ID_LIKE={id_like}"
                elif distro_id == 'gentoo':
                    self._platform = PlatformType.GENTOO
                    self._detection_reason = f"Detected via /etc/os-release: ID={distro_id}, ID_LIKE={id_like}"
                elif 'rhel' in id_like or 'fedora' in id_like:
                    self._platform = PlatformType.RHEL
                    self._detection_reason = f"Detected via /etc/os-release: ID_LIKE={id_like} (RHEL family)"
                elif 'debian' in id_like:
                    self._platform = PlatformType.DEBIAN
                    self._detection_reason = f"Detected via /etc/os-release: ID_LIKE={id_like} (Debian family)"
                else:
                    self._platform = PlatformType.UNKNOWN
                    self._detection_reason = f"Unknown distribution: ID={distro_id}, ID_LIKE={id_like}"

                return
            except Exception as e:
                pass

        # Method 2: Check for distribution-specific files
        distro_files = {
            '/etc/redhat-release': PlatformType.RHEL,
            '/etc/debian_version': PlatformType.DEBIAN,
            '/etc/arch-release': PlatformType.ARCH,
            '/etc/SuSE-release': PlatformType.SUSE,
            '/etc/gentoo-release': PlatformType.GENTOO,
        }

        for file_path, platform_type in distro_files.items():
            if Path(file_path).exists():
                self._platform = platform_type
                self._detection_reason = f"Detected via distribution file: {file_path}"
                try:
                    with open(file_path, 'r') as f:
                        self._distribution = f.read().strip()
                except Exception:
                    self._distribution = platform_type.value
                return

        # Method 3: Check which package manager is available
        package_managers = {
            'dnf': PlatformType.RHEL,
            'yum': PlatformType.RHEL,
            'apt': PlatformType.DEBIAN,
            'apt-get': PlatformType.DEBIAN,
            'pacman': PlatformType.ARCH,
            'zypper': PlatformType.SUSE,
            'emerge': PlatformType.GENTOO,
        }

        for pm, platform_type in package_managers.items():
            try:
                result = subprocess.run(
                    ['which', pm],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    self._platform = platform_type
                    self._detection_reason = f"Detected via package manager availability: {pm}"
                    return
            except Exception:
                continue

        # Fallback to unknown
        self._platform = PlatformType.UNKNOWN
        self._detection_reason = "Could not detect platform using any method"

    @property
    def platform(self) -> PlatformType:
        """Get detected platform type."""
        return self._platform

    @property
    def distribution(self) -> Optional[str]:
        """Get distribution name."""
        return self._distribution

    @property
    def version(self) -> Optional[str]:
        """Get distribution version."""
        return self._version

    @property
    def detection_reason(self) -> Optional[str]:
        """Get reason for platform detection."""
        return self._detection_reason

    def get_commands(self) -> Dict[str, str]:
        """Get platform-specific commands."""
        if self._platform == PlatformType.UNKNOWN:
            # Default to common commands
            return {
                "package_manager": "apt",  # Most common fallback
                "service_manager": "systemctl",
                "firewall": "ufw",
                "network": "nmcli",
            }
        return self.PLATFORM_COMMANDS.get(self._platform, {}).copy()

    def get_package_manager(self) -> str:
        """Get the primary package manager command."""
        commands = self.get_commands()
        return commands.get("package_manager", "apt")

    def get_platform_info(self) -> Dict[str, any]:
        """Get comprehensive platform information."""
        commands = self.get_commands()
        return {
            "platform": self._platform.value if self._platform else "unknown",
            "distribution": self._distribution or "Unknown",
            "version": self._version or "Unknown",
            "detection_reason": self._detection_reason or "Not detected",
            "commands": commands,
            "package_manager": self.get_package_manager(),
        }


"""Tests for platform detection."""

import pytest
from unittest.mock import patch, mock_open
from pathlib import Path

from command_line_assistant.platform_detector import PlatformDetector, PlatformType


def test_platform_detector_initialization():
    """Test platform detector initialization."""
    detector = PlatformDetector()
    assert detector.platform is not None
    assert detector.detection_reason is not None


def test_platform_detector_rhel_detection():
    """Test RHEL platform detection."""
    os_release_content = """ID=fedora
VERSION_ID=43
NAME="Fedora Linux"
ID_LIKE="rhel"
"""
    with patch('pathlib.Path.exists', return_value=True):
        with patch('builtins.open', mock_open(read_data=os_release_content)):
            detector = PlatformDetector()
            # Force re-detection
            detector._detect_platform()
            assert detector.platform == PlatformType.RHEL
            assert "fedora" in detector.detection_reason.lower() or "rhel" in detector.detection_reason.lower()


def test_platform_detector_debian_detection():
    """Test Debian platform detection."""
    os_release_content = """ID=ubuntu
VERSION_ID=22.04
NAME="Ubuntu"
ID_LIKE="debian"
"""
    with patch('pathlib.Path.exists', return_value=True):
        with patch('builtins.open', mock_open(read_data=os_release_content)):
            detector = PlatformDetector()
            detector._detect_platform()
            assert detector.platform == PlatformType.DEBIAN
            assert "ubuntu" in detector.detection_reason.lower() or "debian" in detector.detection_reason.lower()


def test_platform_detector_get_commands():
    """Test getting platform-specific commands."""
    detector = PlatformDetector()
    commands = detector.get_commands()
    assert "package_manager" in commands
    assert "service_manager" in commands
    assert "firewall" in commands
    assert "network" in commands


def test_platform_detector_get_platform_info():
    """Test getting comprehensive platform information."""
    detector = PlatformDetector()
    info = detector.get_platform_info()
    assert "platform" in info
    assert "distribution" in info
    assert "version" in info
    assert "detection_reason" in info
    assert "commands" in info
    assert "package_manager" in info


def test_platform_detector_package_manager():
    """Test getting package manager."""
    detector = PlatformDetector()
    pm = detector.get_package_manager()
    assert pm in ["dnf", "yum", "apt", "apt-get", "pacman", "zypper", "emerge"]



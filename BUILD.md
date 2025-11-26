# Building Command Line Assistant

## Prerequisites

### For Python Package Build
- Python 3.8 or higher
- `build` package: `pip install build`

### For RPM Build
- `rpmbuild` (usually from `rpm-build` package)
- Python 3.8 or higher
- Build dependencies as specified in the spec file

### For DEB Build
- `dpkg-buildpackage` (from `dpkg-dev` package)
- `debhelper` and `dh-python`
- Python 3.8 or higher
- Build dependencies as specified in debian/control

### For Arch Build
- `makepkg` (from `pacman` package)
- `base-devel` package group
- Python 3.8 or higher

### For Gentoo Build
- Gentoo Portage system
- `ebuild` command
- Python 3.8 or higher

## Building Python Package

```bash
make build
```

This creates:
- `dist/command_line_assistant-0.1.0.tar.gz` (source distribution)
- `dist/command_line_assistant-0.1.0-py3-none-any.whl` (wheel)

## Building RPM

### Step 1: Create Source Tarball

```bash
make tarball
```

This creates `command-line-assistant-0.1.0.tar.gz` in the project root.

### Step 2: Set Up RPM Build Environment

If you don't have `~/rpmbuild` directory:

```bash
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
```

### Step 3: Copy Files to RPM Build Directory

```bash
cp command-line-assistant-0.1.0.tar.gz ~/rpmbuild/SOURCES/
cp packaging/command-line-assistant.spec ~/rpmbuild/SPECS/
cp packaging/command-line-assistant.service ~/rpmbuild/SOURCES/
cp packaging/config.toml ~/rpmbuild/SOURCES/
```

### Step 4: Build RPM

```bash
cd ~/rpmbuild/SPECS
rpmbuild -ba command-line-assistant.spec
```

Or use the Makefile:

```bash
make rpm
```

The RPM will be created in `~/rpmbuild/RPMS/noarch/`

### Step 5: Build Source RPM (Optional)

```bash
make srpm
```

Or manually:

```bash
cd ~/rpmbuild/SPECS
rpmbuild -bs command-line-assistant.spec
```

The SRPM will be created in `~/rpmbuild/SRPMS/`

## Building DEB Package

### Prerequisites

Install build dependencies on Debian/Ubuntu:

```bash
sudo apt-get install build-essential debhelper dh-python python3-all python3-build python3-installer python3-wheel python3-setuptools
```

### Build DEB Package

```bash
make deb
```

Or manually:

```bash
# Create source tarball
make tarball

# Extract and prepare
mkdir -p debuild
cd debuild
tar -xzf ../command-line-assistant-*.tar.gz
cd command-line-assistant-*
cp -r ../../packaging/debian .

# Build package
dpkg-buildpackage -us -uc -b
```

The DEB package will be created in the `debuild/` directory.

## Building Arch Package

### Prerequisites

Install build dependencies on Arch Linux:

```bash
sudo pacman -S base-devel python python-build python-installer python-wheel python-setuptools
```

### Build Arch Package

```bash
make arch
```

Or manually:

```bash
# Create source tarball
make tarball

# Copy files to build directory
mkdir -p archbuild
cp command-line-assistant-*.tar.gz archbuild/
cp packaging/command-line-assistant.service archbuild/
cp packaging/config.toml archbuild/
cp packaging/PKGBUILD archbuild/

# Build package
cd archbuild
makepkg -s --cleanbuild --skipinteg
```

The Arch package will be created in the `archbuild/` directory.

## Building Gentoo Package

### Prerequisites

Gentoo ebuilds require a full Gentoo environment with Portage configured.

### Create Ebuild Manifest

```bash
make gentoo
```

This creates the manifest file for the ebuild. The ebuild file is located at:
`packaging/command-line-assistant/command-line-assistant-0.2.4.ebuild`

To use the ebuild in a Gentoo system, copy it to your local overlay or the appropriate Portage location.

## Building All Packages

Build all package types at once:

```bash
make all-packages
```

This will build RPM, DEB, and Arch packages.

## Installation

### From RPM

**Recommended (automatically installs dependencies):**

```bash
sudo dnf install ~/rpmbuild/RPMS/noarch/command-line-assistant-0.1.0-1.*.rpm
```

Or on older systems:

```bash
sudo yum install ~/rpmbuild/RPMS/noarch/command-line-assistant-0.1.0-1.*.rpm
```

**Note:** Using `dnf install` or `yum install` will automatically resolve and install all required dependencies (python3, python3-requests, python3-click, python3-tomli, systemd).

If you must use `rpm -ivh`, install dependencies first:

```bash
sudo dnf install python3 python3-requests python3-click python3-tomli systemd
sudo rpm -ivh ~/rpmbuild/RPMS/noarch/command-line-assistant-0.1.0-1.*.rpm
```

### From DEB Package

**Recommended (automatically installs dependencies):**

```bash
sudo apt-get install ./debuild/command-line-assistant_*.deb
```

Or using dpkg (install dependencies first):

```bash
sudo apt-get install python3 python3-requests python3-click python3-tomli systemd
sudo dpkg -i debuild/command-line-assistant_*.deb
```

### From Arch Package

```bash
sudo pacman -U archbuild/command-line-assistant-*.pkg.tar.zst
```

Or install dependencies first:

```bash
sudo pacman -S python python-requests python-click python-tomli systemd
sudo pacman -U archbuild/command-line-assistant-*.pkg.tar.zst
```

### From Gentoo Ebuild

Copy the ebuild to your local overlay and emerge:

```bash
# Copy ebuild to local overlay
cp -r packaging/command-line-assistant /usr/local/portage/app-admin/

# Update Portage
sudo ebuild /usr/local/portage/app-admin/command-line-assistant/command-line-assistant-0.2.4.ebuild manifest

# Install
sudo emerge app-admin/command-line-assistant
```

### From Python Package

```bash
pip install dist/command_line_assistant-0.2.4-py3-none-any.whl
```

Or from source:

```bash
pip install -e .
```

## Verification

After installation, verify the installation:

```bash
# Check CLI tool
cla --version

# Check daemon binary
clad --help

# Check service (if installed via RPM)
systemctl status command-line-assistant
```

## Docker Testing

Test packages in isolated Docker containers for each platform.

### Prerequisites

- Docker installed and running
- Packages built (use `make all-packages` or individual build targets)

### Test Individual Packages

Test each package type:

```bash
# Test DEB package
make test-deb

# Test Arch package
make test-arch

# Test Gentoo package
make test-gentoo

# Test RPM package
make test-rpm
```

### Test All Packages

Test all package types:

```bash
make test-all
```

### Manual Docker Testing

You can also use Docker Compose to test all platforms:

```bash
cd docker
docker-compose up --build
```

Or test individual platforms:

```bash
# Test Debian
docker build -f docker/Dockerfile.debian -t cla-test-debian .
docker run --rm cla-test-debian

# Test Ubuntu
docker build -f docker/Dockerfile.ubuntu -t cla-test-ubuntu .
docker run --rm cla-test-ubuntu

# Test Arch
docker build -f docker/Dockerfile.arch -t cla-test-arch .
docker run --rm cla-test-arch

# Test Fedora
docker build -f docker/Dockerfile.fedora -t cla-test-fedora .
docker run --rm cla-test-fedora

# Test RHEL
docker build -f docker/Dockerfile.rhel -t cla-test-rhel .
docker run --rm cla-test-rhel

# Test SUSE
docker build -f docker/Dockerfile.suse -t cla-test-suse .
docker run --rm cla-test-suse
```

The test script verifies:
- CLI tool (`cla`) is available and works
- Daemon binary (`clad`) is available
- Systemd service file is installed
- Config file is installed
- Python module can be imported

## Troubleshooting

### Missing Dependencies

**RPM build:**
```bash
# On RHEL/Fedora
sudo dnf install rpm-build python3-devel python3-build python3-installer python3-wheel python3-setuptools
```

**DEB build:**
```bash
# On Debian/Ubuntu
sudo apt-get install build-essential debhelper dh-python python3-all python3-build python3-installer python3-wheel python3-setuptools
```

**Arch build:**
```bash
# On Arch Linux
sudo pacman -S base-devel python python-build python-installer python-wheel python-setuptools
```

### Build Errors

- Ensure all source files are present in the tarball
- Check that packaging files reference correct source file names
- Verify Python version compatibility
- For DEB builds, ensure debian/ directory structure is correct
- For Arch builds, verify PKGBUILD syntax and file paths
- For Gentoo builds, ensure ebuild follows Gentoo conventions

### Docker Testing Issues

- Ensure Docker is running: `docker ps`
- Check that packages are built before testing
- For Arch builds in Docker, may need `--privileged` flag
- Gentoo Docker testing requires a full Gentoo environment setup


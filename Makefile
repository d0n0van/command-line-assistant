.PHONY: help build clean install test rpm srpm deb arch gentoo all-packages test-deb test-arch test-gentoo test-rpm test-all

PYTHON := python3
PACKAGE_NAME := command-line-assistant
VERSION := $(shell grep -m1 "^version = " pyproject.toml | sed 's/.*"\(.*\)".*/\1/')
RELEASE := $(shell grep -m1 "^Release:" packaging/command-line-assistant.spec | awk '{print $$2}' | sed 's/%{?dist}//')
DIST := $(shell rpm --eval '%{?dist}' | sed 's/^\.//')
FULL_VERSION := $(VERSION)-$(RELEASE)$(if $(DIST),.$(DIST),)

SRCDIR := $(PACKAGE_NAME)-$(VERSION)
TARBALL := $(SRCDIR).tar.gz
RPMBUILD_DIR := $$HOME/rpmbuild
SPECFILE := packaging/command-line-assistant.spec
DEB_BUILD_DIR := debuild
ARCH_BUILD_DIR := archbuild

help:
	@echo "Available targets:"
	@echo "  build         - Build Python package"
	@echo "  clean         - Clean build artifacts"
	@echo "  install       - Install package locally"
	@echo "  test          - Run tests"
	@echo "  rpm           - Build RPM package"
	@echo "  srpm          - Build source RPM"
	@echo "  deb           - Build DEB package"
	@echo "  arch          - Build Arch package"
	@echo "  gentoo        - Create Gentoo ebuild manifest"
	@echo "  all-packages  - Build all package types"
	@echo "  tarball       - Create source tarball"
	@echo "  test-deb      - Test DEB package in Docker"
	@echo "  test-arch     - Test Arch package in Docker"
	@echo "  test-gentoo   - Test Gentoo package in Docker"
	@echo "  test-rpm      - Test RPM package in Docker"
	@echo "  test-all      - Test all packages in Docker"

build:
	$(PYTHON) -m build

clean:
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf $(SRCDIR) $(TARBALL)
	rm -rf $(DEB_BUILD_DIR) $(ARCH_BUILD_DIR)
	rm -rf packaging/command-line-assistant/*.ebuild
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

install:
	$(PYTHON) -m pip install -e .

test:
	$(PYTHON) -m pytest tests/

tarball: clean
	@echo "Creating source tarball..."
	mkdir -p $(SRCDIR)
	cp -r command_line_assistant $(SRCDIR)/
	cp -r packaging $(SRCDIR)/
	cp pyproject.toml requirements.txt README.md LICENSE $(SRCDIR)/
	cp setup.py $(SRCDIR)/ 2>/dev/null || true
	tar -czf $(TARBALL) $(SRCDIR)
	rm -rf $(SRCDIR)
	@echo "Created $(TARBALL)"

rpm: tarball
	@echo "Building RPM..."
	@mkdir -p $(RPMBUILD_DIR)/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
	cp $(TARBALL) $(RPMBUILD_DIR)/SOURCES/
	cp $(SPECFILE) $(RPMBUILD_DIR)/SPECS/
	cp packaging/command-line-assistant.service $(RPMBUILD_DIR)/SOURCES/
	cp packaging/config.toml $(RPMBUILD_DIR)/SOURCES/
	cd $(RPMBUILD_DIR)/SPECS && rpmbuild -ba command-line-assistant.spec
	@echo "RPM built in $(RPMBUILD_DIR)/RPMS/"

srpm: tarball
	@echo "Building source RPM..."
	@mkdir -p $(RPMBUILD_DIR)/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
	cp $(TARBALL) $(RPMBUILD_DIR)/SOURCES/
	cp $(SPECFILE) $(RPMBUILD_DIR)/SPECS/
	cp packaging/command-line-assistant.service $(RPMBUILD_DIR)/SOURCES/
	cp packaging/config.toml $(RPMBUILD_DIR)/SOURCES/
	cd $(RPMBUILD_DIR)/SPECS && rpmbuild -bs command-line-assistant.spec
	@echo "Source RPM built in $(RPMBUILD_DIR)/SRPMS/"

deb: tarball
	@echo "Building DEB package..."
	@if command -v dpkg-buildpackage >/dev/null 2>&1; then \
		mkdir -p $(DEB_BUILD_DIR); \
		cd $(DEB_BUILD_DIR) && tar -xzf ../$(TARBALL); \
		cd $(DEB_BUILD_DIR)/$(SRCDIR) && cp -r ../../packaging/debian .; \
		cd $(DEB_BUILD_DIR)/$(SRCDIR) && dpkg-buildpackage -us -uc -b; \
		echo "DEB package built in $(DEB_BUILD_DIR)/"; \
	else \
		echo "dpkg-buildpackage not found, using Docker..."; \
		$(MAKE) deb-docker; \
	fi

deb-docker: tarball
	@echo "Building DEB package in Docker..."
	@mkdir -p $(DEB_BUILD_DIR)
	@docker build -f docker/Dockerfile.build-deb -t cla-build-deb .
	@docker create --name cla-deb-temp cla-build-deb
	@docker cp cla-deb-temp:/build/command-line-assistant_0.2.4-1_all.deb $(DEB_BUILD_DIR)/ 2>/dev/null || true
	@docker cp cla-deb-temp:/build/command-line-assistant_0.2.4-1_amd64.changes $(DEB_BUILD_DIR)/ 2>/dev/null || true
	@docker rm cla-deb-temp
	@echo "DEB package built in $(DEB_BUILD_DIR)/"

arch: tarball
	@echo "Building Arch package..."
	@if command -v makepkg >/dev/null 2>&1; then \
		mkdir -p $(ARCH_BUILD_DIR); \
		cp $(TARBALL) $(ARCH_BUILD_DIR)/; \
		cp packaging/command-line-assistant.service $(ARCH_BUILD_DIR)/; \
		cp packaging/config.toml $(ARCH_BUILD_DIR)/; \
		cp packaging/PKGBUILD $(ARCH_BUILD_DIR)/; \
		cd $(ARCH_BUILD_DIR) && makepkg -s --cleanbuild --skipinteg; \
		echo "Arch package built in $(ARCH_BUILD_DIR)/"; \
	else \
		echo "makepkg not found, using Docker..."; \
		$(MAKE) arch-docker; \
	fi

arch-docker: tarball
	@echo "Building Arch package in Docker..."
	@mkdir -p $(ARCH_BUILD_DIR)
	@docker build -f docker/Dockerfile.build-arch -t cla-build-arch .
	@docker run --rm -v $(PWD)/$(ARCH_BUILD_DIR):/output cla-build-arch
	@echo "Arch package built in $(ARCH_BUILD_DIR)/"

gentoo:
	@echo "Creating Gentoo ebuild manifest..."
	@cd packaging/command-line-assistant && ebuild command-line-assistant-$(VERSION).ebuild manifest
	@echo "Gentoo ebuild manifest created"

all-packages: rpm deb arch
	@echo "All packages built"

test-deb: deb
	@echo "Testing DEB package in Docker..."
	docker build -f docker/Dockerfile.debian -t cla-test-debian .
	docker run --rm cla-test-debian

test-arch: arch
	@echo "Testing Arch package in Docker..."
	docker build -f docker/Dockerfile.arch -t cla-test-arch .
	docker run --rm --privileged cla-test-arch

test-gentoo: gentoo
	@echo "Testing Gentoo package in Docker..."
	docker build -f docker/Dockerfile.gentoo -t cla-test-gentoo .
	docker run --rm cla-test-gentoo

test-rpm: rpm
	@echo "Testing RPM package in Docker..."
	@mkdir -p docker/rpm-packages
	@cp $(RPMBUILD_DIR)/RPMS/noarch/command-line-assistant-*.rpm docker/rpm-packages/ 2>/dev/null || true
	docker build -f docker/Dockerfile.fedora -t cla-test-fedora .
	docker run --rm cla-test-fedora
	@rm -rf docker/rpm-packages

test-all: test-deb test-arch test-gentoo test-rpm
	@echo "All package tests completed"


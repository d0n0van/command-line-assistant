%global pyproject_buildrequires python3-build python3-installer python3-wheel
%global pyproject_buildrequires_extras dev

%global srcname command-line-assistant

Name:           command-line-assistant
Version:        0.2.6
Release:        1%{?dist}
Summary:        Command-line assistant powered by Ollama
License:        Apache-2.0
URL:             https://github.com/rhel-lightspeed/command-line-assistant
Source0:        %{name}-%{version}.tar.gz
Source1:        config.toml

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-build
BuildRequires:  python3-installer
BuildRequires:  python3-wheel
BuildRequires:  python3-setuptools
Requires:       python3
Requires:       python3-requests
Requires:       python3-click
# tomli is only needed for Python < 3.11, but including it won't hurt
Requires:       python3-tomli

%description
Command-line assistant that provides AI-driven assistance using Ollama.
Configure Ollama endpoint, model, and temperature via configuration file.
Includes CLI tool for AI-driven assistance.

%prep
%autosetup -n %{srcname}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files command_line_assistant

# Install default config
install -d %{buildroot}%{_sysconfdir}/xdg/command-line-assistant
install -m 644 %{SOURCE1} %{buildroot}%{_sysconfdir}/xdg/command-line-assistant/config.toml

%post
# Verify and install dependencies if missing (dnf/yum will handle this automatically,
# but this ensures they're present even if installed via rpm -ivh)
if ! rpm -q python3-requests >/dev/null 2>&1; then
    echo "Warning: python3-requests is not installed. Please install dependencies:" >&2
    echo "  sudo dnf install python3-requests python3-click python3-tomli" >&2
fi

%files
%license LICENSE
%doc README.md
%{_bindir}/cla
%{python3_sitelib}/command_line_assistant
%{python3_sitelib}/command_line_assistant-*.dist-info
%config(noreplace) %{_sysconfdir}/xdg/command-line-assistant/config.toml

%changelog
* Tue Nov 26 2024 Command Line Assistant Contributors <command-line-assistant@example.com> - 0.2.6-1
- Version bump to 0.2.6
- Added conversation history context in interactive mode
- Interactive mode now maintains context across multiple queries
- Added 'clear' command to clear conversation history

* Tue Nov 26 2024 Command Line Assistant Contributors <command-line-assistant@example.com> - 0.2.5-1
- Version bump to 0.2.5
- Added multi-platform packaging support (DEB, RPM, Arch, Gentoo)
- Added Docker-based build and testing infrastructure

* Tue Nov 26 2024 Command Line Assistant Contributors <command-line-assistant@example.com> - 0.2.4-1
- Added command output analysis and reaction feature
- AI now analyzes command output and executes follow-up commands automatically
- Enhanced iterative execution with max iterations limit
- Improved error handling with automatic recovery

* Tue Nov 26 2024 Command Line Assistant Contributors <command-line-assistant@example.com> - 0.2.3-1
- Added command output analysis and reaction feature
- AI now analyzes command output and automatically reacts to errors
- Added iterative execution loop for multi-step tasks
- Enhanced system prompt for output analysis
- Default model changed to mistral:instruct

* Tue Nov 26 2024 Command Line Assistant Contributors <command-line-assistant@example.com> - 0.2.2-1
- Added command output analysis and reaction feature
- AI now analyzes command output and errors, reacts with follow-up commands
- Iterative execution loop with max iterations limit
- Enhanced system prompt for output analysis
- Default model changed to mistral:instruct

* Tue Nov 26 2024 Command Line Assistant Contributors <command-line-assistant@example.com> - 0.2.1-1
- Added command execution feature (--execute flag)
- Enhanced CLI with thinking process display
- Added safety checks for dangerous commands
- Improved user experience with colored output

* Tue Nov 26 2024 Command Line Assistant Contributors <command-line-assistant@example.com> - 0.1.0-1
- Initial release


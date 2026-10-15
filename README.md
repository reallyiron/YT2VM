# YT2VM©: YouTube to VM

A lightweight Python project that connects YouTube-related workflows to a virtual machine setup. It is designed to help automate VM-based tasks, stream management, and control flows in a simple and open-source way.

# What does it do?

YT2VM is a project that brings together several tools to make a VM-centered YouTube workflow easier to manage. It can be used to:

- Start and control virtual machines using VirtualBox or VMWare
- Connect with OBS for stream or scene automation
- Interface with chat-driven tools using `pytchat`
- Run a lightweight web-based control layer with Flask
- Support cross-platform usage across Windows, macOS, and Linux

In short, this project is meant to help automate the parts of a YouTube or streaming workflow that are usually managed through a VM environment, making setup and control more convenient.

# Installation and Dependencies

For working with this script, you need to install several Python packages. This can be done with the following command in your terminal:

```bash
pip install virtualbox Flask pytchat obsws-python pywin32
```

Attention: `pywin32` works on Windows only and should be installed if you use the script on Windows.

# Features

- Cross-Platform: Supports Windows, macOS, and Linux.
- Open-Source: Full source code is open to everyone.
- VM Integration: Designed to work with VirtualBox-powered environments, but does work with VMWare too.
- OBS Support: Can integrate with OBS WebSocket for automation.
- Flask-Based Control: Includes a lightweight Python web interface.

# FAQ

## Do I have to credit you?

No. It is free to use forever.

## Is this script malware?

No. All source code is open to everyone, so you can inspect it yourself. There are no stealers or malicious components in this repository.

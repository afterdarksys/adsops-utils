#!/usr/bin/env python3
"""
Oracle Cloud to Ansible Generator

Reads Oracle Cloud configuration and generates Ansible playbooks/inventory.
Designed for accessibility with screen reader friendly output.

Usage:
    generate_ansible.py --compartment ocid... --output ./ansible
    generate_ansible.py --inventory                # Generate inventory only
    generate_ansible.py --playbooks                # Generate playbooks only
    generate_ansible.py --all --output ./ansible   # Generate everything
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import oci
except ImportError:
    print("Error: OCI Python SDK not installed.")
    print("Install with: pip install oci")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: PyYAML not installed.")
    print("Install with: pip install pyyaml")
    sys.exit(1)


def speak(message: str):
    """Print message with timestamp for screen readers."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp."""
    print(message)
    sys.stdout.flush()


def get_oci_config(profile: str = "DEFAULT") -> dict:
    """Load OCI SDK configuration."""
    config_path = Path.home() / ".oci" / "config"
    if not config_path.exists():
        print(f"Error: OCI config not found at {config_path}")
        print("Run 'oci setup config' to create it.")
        sys.exit(1)
    return oci.config.from_file(profile_name=profile)


def sanitize_name(name: str) -> str:
    """Convert name to valid Ansible identifier."""
    result = ""
    for char in name.lower():
        if char.isalnum() or char == "_":
            result += char
        else:
            result += "_"
    while "__" in result:
        result = result.replace("__", "_")
    return result.strip("_")


def get_instance_ip(compute_client, network_client, instance) -> dict:
    """Get IP addresses for an instance."""
    ips = {"private": None, "public": None}

    try:
        vnics = compute_client.list_vnic_attachments(
            compartment_id=instance.compartment_id,
            instance_id=instance.id
        ).data

        for vnic_att in vnics:
            if vnic_att.lifecycle_state == "ATTACHED":
                vnic = network_client.get_vnic(vnic_att.vnic_id).data
                ips["private"] = vnic.private_ip
                ips["public"] = vnic.public_ip
                break
    except Exception:
        pass

    return ips


def generate_inventory(compute_client, network_client, compartment_id: str) -> dict:
    """Generate Ansible inventory from OCI instances."""
    speak("Generating Ansible inventory...")

    instances = compute_client.list_instances(compartment_id=compartment_id).data
    running_instances = [i for i in instances if i.lifecycle_state == "RUNNING"]

    inventory = {
        "all": {
            "hosts": {},
            "children": {
                "oci_instances": {
                    "hosts": {}
                },
                "oracle_linux": {
                    "hosts": {}
                },
                "ubuntu": {
                    "hosts": {}
                }
            },
            "vars": {
                "ansible_user": "opc",
                "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
                "ansible_python_interpreter": "/usr/bin/python3"
            }
        }
    }

    for instance in running_instances:
        name = sanitize_name(instance.display_name)
        ips = get_instance_ip(compute_client, network_client, instance)

        # Prefer public IP, fall back to private
        ansible_host = ips["public"] or ips["private"]
        if not ansible_host:
            speak(f"  Skipping {instance.display_name}: no IP address found")
            continue

        host_vars = {
            "ansible_host": ansible_host,
            "oci_instance_id": instance.id,
            "oci_shape": instance.shape,
            "oci_availability_domain": instance.availability_domain,
            "private_ip": ips["private"],
            "public_ip": ips["public"]
        }

        if instance.shape_config:
            host_vars["oci_ocpus"] = instance.shape_config.ocpus
            host_vars["oci_memory_gb"] = instance.shape_config.memory_in_gbs

        # Add to all hosts
        inventory["all"]["hosts"][name] = host_vars
        inventory["all"]["children"]["oci_instances"]["hosts"][name] = {}

        # Categorize by OS (based on shape - ARM typically Ubuntu, x86 typically Oracle Linux)
        if "A1" in instance.shape:
            inventory["all"]["children"]["ubuntu"]["hosts"][name] = {
                "ansible_user": "ubuntu"
            }
        else:
            inventory["all"]["children"]["oracle_linux"]["hosts"][name] = {}

        speak(f"  Added host: {name} ({ansible_host})")

    speak(f"  Total hosts: {len(inventory['all']['hosts'])}")
    return inventory


def generate_provision_playbook() -> dict:
    """Generate a basic provisioning playbook."""
    return {
        "name": "Provision OCI instances",
        "hosts": "oci_instances",
        "become": True,
        "vars": {
            "packages": [
                "vim",
                "git",
                "curl",
                "wget",
                "htop",
                "tmux"
            ]
        },
        "tasks": [
            {
                "name": "Update package cache (Debian/Ubuntu)",
                "apt": {
                    "update_cache": True,
                    "cache_valid_time": 3600
                },
                "when": "ansible_os_family == 'Debian'"
            },
            {
                "name": "Update package cache (RHEL/Oracle Linux)",
                "yum": {
                    "update_cache": True
                },
                "when": "ansible_os_family == 'RedHat'"
            },
            {
                "name": "Install common packages (Debian/Ubuntu)",
                "apt": {
                    "name": "{{ packages }}",
                    "state": "present"
                },
                "when": "ansible_os_family == 'Debian'"
            },
            {
                "name": "Install common packages (RHEL/Oracle Linux)",
                "yum": {
                    "name": "{{ packages }}",
                    "state": "present"
                },
                "when": "ansible_os_family == 'RedHat'"
            },
            {
                "name": "Set timezone",
                "timezone": {
                    "name": "UTC"
                }
            },
            {
                "name": "Ensure SSH directory exists",
                "file": {
                    "path": "/root/.ssh",
                    "state": "directory",
                    "mode": "0700"
                }
            }
        ]
    }


def generate_security_playbook() -> dict:
    """Generate a security hardening playbook."""
    return {
        "name": "Security hardening for OCI instances",
        "hosts": "oci_instances",
        "become": True,
        "tasks": [
            {
                "name": "Disable root SSH login",
                "lineinfile": {
                    "path": "/etc/ssh/sshd_config",
                    "regexp": "^PermitRootLogin",
                    "line": "PermitRootLogin no"
                },
                "notify": "Restart SSH"
            },
            {
                "name": "Disable password authentication",
                "lineinfile": {
                    "path": "/etc/ssh/sshd_config",
                    "regexp": "^PasswordAuthentication",
                    "line": "PasswordAuthentication no"
                },
                "notify": "Restart SSH"
            },
            {
                "name": "Enable firewall (UFW for Ubuntu)",
                "ufw": {
                    "state": "enabled",
                    "policy": "deny"
                },
                "when": "ansible_os_family == 'Debian'"
            },
            {
                "name": "Allow SSH through firewall",
                "ufw": {
                    "rule": "allow",
                    "port": "22",
                    "proto": "tcp"
                },
                "when": "ansible_os_family == 'Debian'"
            },
            {
                "name": "Enable firewalld (Oracle Linux)",
                "service": {
                    "name": "firewalld",
                    "state": "started",
                    "enabled": True
                },
                "when": "ansible_os_family == 'RedHat'"
            }
        ],
        "handlers": [
            {
                "name": "Restart SSH",
                "service": {
                    "name": "sshd",
                    "state": "restarted"
                }
            }
        ]
    }


def generate_docker_playbook() -> dict:
    """Generate Docker installation playbook."""
    return {
        "name": "Install Docker on OCI instances",
        "hosts": "oci_instances",
        "become": True,
        "tasks": [
            {
                "name": "Install Docker dependencies (Ubuntu)",
                "apt": {
                    "name": [
                        "apt-transport-https",
                        "ca-certificates",
                        "curl",
                        "gnupg",
                        "lsb-release"
                    ],
                    "state": "present"
                },
                "when": "ansible_os_family == 'Debian'"
            },
            {
                "name": "Add Docker GPG key (Ubuntu)",
                "apt_key": {
                    "url": "https://download.docker.com/linux/ubuntu/gpg",
                    "state": "present"
                },
                "when": "ansible_os_family == 'Debian'"
            },
            {
                "name": "Add Docker repository (Ubuntu)",
                "apt_repository": {
                    "repo": "deb [arch=arm64] https://download.docker.com/linux/ubuntu {{ ansible_distribution_release }} stable",
                    "state": "present"
                },
                "when": "ansible_os_family == 'Debian' and ansible_architecture == 'aarch64'"
            },
            {
                "name": "Install Docker (Ubuntu)",
                "apt": {
                    "name": [
                        "docker-ce",
                        "docker-ce-cli",
                        "containerd.io",
                        "docker-compose-plugin"
                    ],
                    "state": "present",
                    "update_cache": True
                },
                "when": "ansible_os_family == 'Debian'"
            },
            {
                "name": "Install Docker (Oracle Linux)",
                "yum": {
                    "name": [
                        "docker-engine",
                        "docker-cli"
                    ],
                    "state": "present"
                },
                "when": "ansible_os_family == 'RedHat'"
            },
            {
                "name": "Start and enable Docker",
                "service": {
                    "name": "docker",
                    "state": "started",
                    "enabled": True
                }
            },
            {
                "name": "Add user to docker group",
                "user": {
                    "name": "{{ ansible_user }}",
                    "groups": "docker",
                    "append": True
                }
            }
        ]
    }


def generate_oci_collection_requirements() -> dict:
    """Generate Ansible Galaxy requirements for OCI collection."""
    return {
        "collections": [
            {
                "name": "oracle.oci",
                "version": ">=4.0.0"
            }
        ]
    }


def generate_ansible_cfg() -> str:
    """Generate ansible.cfg file."""
    return """[defaults]
inventory = inventory.yml
host_key_checking = False
retry_files_enabled = False
stdout_callback = yaml
interpreter_python = auto_silent

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=no
pipelining = True
"""


def run_export(args):
    """Run the Ansible export."""
    speak("Oracle Cloud to Ansible Export")
    speak("")

    oci_config = get_oci_config(args.profile)
    compartment_id = args.compartment or oci_config["tenancy"]

    speak(f"Compartment: {compartment_id}")
    speak(f"Output directory: {args.output}")
    speak("")

    # Create output directory structure
    output_path = Path(args.output).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "playbooks").mkdir(exist_ok=True)
    (output_path / "group_vars").mkdir(exist_ok=True)
    (output_path / "host_vars").mkdir(exist_ok=True)

    # Initialize clients
    compute_client = oci.core.ComputeClient(oci_config)
    network_client = oci.core.VirtualNetworkClient(oci_config)

    try:
        # Generate inventory
        if args.inventory or args.all or not args.playbooks:
            inventory = generate_inventory(compute_client, network_client, compartment_id)

            inventory_file = output_path / "inventory.yml"
            with open(inventory_file, "w") as f:
                yaml.dump(inventory, f, default_flow_style=False, sort_keys=False)
            speak(f"Written: {inventory_file}")

        # Generate playbooks
        if args.playbooks or args.all or not args.inventory:
            # Provision playbook
            provision = generate_provision_playbook()
            provision_file = output_path / "playbooks" / "provision.yml"
            with open(provision_file, "w") as f:
                yaml.dump([provision], f, default_flow_style=False, sort_keys=False)
            speak(f"Written: {provision_file}")

            # Security playbook
            security = generate_security_playbook()
            security_file = output_path / "playbooks" / "security.yml"
            with open(security_file, "w") as f:
                yaml.dump([security], f, default_flow_style=False, sort_keys=False)
            speak(f"Written: {security_file}")

            # Docker playbook
            docker = generate_docker_playbook()
            docker_file = output_path / "playbooks" / "docker.yml"
            with open(docker_file, "w") as f:
                yaml.dump([docker], f, default_flow_style=False, sort_keys=False)
            speak(f"Written: {docker_file}")

            # Site playbook (imports all others)
            site = [
                {"import_playbook": "playbooks/provision.yml"},
                {"import_playbook": "playbooks/security.yml"},
                {"import_playbook": "playbooks/docker.yml"}
            ]
            site_file = output_path / "site.yml"
            with open(site_file, "w") as f:
                yaml.dump(site, f, default_flow_style=False, sort_keys=False)
            speak(f"Written: {site_file}")

        # Generate requirements.yml
        requirements = generate_oci_collection_requirements()
        req_file = output_path / "requirements.yml"
        with open(req_file, "w") as f:
            yaml.dump(requirements, f, default_flow_style=False, sort_keys=False)
        speak(f"Written: {req_file}")

        # Generate ansible.cfg
        cfg_file = output_path / "ansible.cfg"
        with open(cfg_file, "w") as f:
            f.write(generate_ansible_cfg())
        speak(f"Written: {cfg_file}")

        # Generate group_vars/all.yml
        group_vars = {
            "oci_compartment_id": compartment_id,
            "oci_region": oci_config.get("region", "us-ashburn-1"),
            "oci_tenancy_id": oci_config.get("tenancy", "")
        }
        group_vars_file = output_path / "group_vars" / "all.yml"
        with open(group_vars_file, "w") as f:
            yaml.dump(group_vars, f, default_flow_style=False, sort_keys=False)
        speak(f"Written: {group_vars_file}")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)

    speak("")
    speak("Export complete!")
    speak_plain("")
    speak_plain("Next steps:")
    speak_plain(f"  1. cd {args.output}")
    speak_plain("  2. Review and modify inventory.yml")
    speak_plain("  3. Install OCI collection: ansible-galaxy collection install -r requirements.yml")
    speak_plain("  4. Test connectivity: ansible all -m ping")
    speak_plain("  5. Run playbook: ansible-playbook site.yml")
    speak_plain("")
    speak_plain("Generated playbooks:")
    speak_plain("  - provision.yml   : Install common packages")
    speak_plain("  - security.yml    : Security hardening")
    speak_plain("  - docker.yml      : Docker installation")
    speak_plain("  - site.yml        : Run all playbooks")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ansible from Oracle Cloud resources. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    generate_ansible.py --output ./ansible
    generate_ansible.py --compartment ocid1... --output ./ansible
    generate_ansible.py --inventory --output ./ansible
    generate_ansible.py --playbooks --output ./ansible
    generate_ansible.py --all --output ./ansible

Screen Reader Notes:
    Progress messages include timestamps.
    Output files are listed as they are created.
"""
    )

    parser.add_argument(
        "--profile", "-p",
        default="DEFAULT",
        help="OCI config profile (default: DEFAULT)"
    )
    parser.add_argument(
        "--compartment", "-c",
        help="Compartment OCID (default: tenancy root)"
    )
    parser.add_argument(
        "--output", "-o",
        default="./ansible",
        help="Output directory (default: ./ansible)"
    )
    parser.add_argument(
        "--inventory", "-i",
        action="store_true",
        help="Generate inventory only"
    )
    parser.add_argument(
        "--playbooks",
        action="store_true",
        help="Generate playbooks only"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Generate everything"
    )

    args = parser.parse_args()

    try:
        run_export(args)
    except KeyboardInterrupt:
        speak("")
        speak("Export cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

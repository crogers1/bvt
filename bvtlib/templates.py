EMPTY_TEMPLATE="""{
    "type": "svm",
    "ui-selectable": "false",
    "slot": "-1",
    "config": {
      "hvm": "true",
      "pae": "true",
      "acpi": "true",
      "apic": "true",
      "viridian": "true",
      "hap": "true",
      "nx": "true",
      "v4v": "true",
      "sound": "ac97",
      "memory": "1024",
      "display": "none",
      "boot": "cd",
      "flask-label": "system_u:system_r:hvm_guest_t",
      "vcpus": "1",
      "disk": {
        "0": {
      "path": "\/storage\/disks\/",
          "type": "vhd","mode": "w",
          "device": "hda",
          "devtype": "disk",
          "shared": "true"
        }
      }
    },
    "hidden": "true",
    "hidden-in-ui": "true",
    "domstore-read-access": "true",
    "domstore-write-access": "true"
}
"""

MAX_BYPASS_TEMPLATE="""{
   "name": "testvm",
   "type": "svm",
   "slot": "-1",
   "v4v-firewall-rules": {
     "0": "myself -> 0:4346709",
     "1": "myself -> 0:80",
     "2": "myself-if-seamless:14494 -> 0:4494",
     "3": "seamless -> myself-if-seamless:100",
     "4": "seamless:11494 -> myself-if-seamless:1494",
     "5": "myself -> 0:5556",
     "6": "my-stubdom -> 0:5555",
     "7": "my-stubdom -> 0:4001",
     "8": "my-stubdom -> 0:4002",
     "9": "my-stubdom -> 0:5000",
     "10": "my-stubdom -> 0:5001",
     "11": "my-stubdom -> 0:5559"
   },
    "description": "thinvm",
    "os": "linux",
    "ui-selectable": "false",
    "xci-cpuid-signature": "false",
    "stubdom": "true",
    "policies": {
      "audio-rec": "false"
    },
    "config": {
      "notify": "dbus",
      "hvm": "true",
      "pae": "true",
      "acpi": "true",
      "apic": "true",
      "viridian": "false",
      "hap": "true",
      "nx": "true",
      "v4v": "true",
      "sound": "ac97",
      "memory": "256",
      "display": "none",
      "boot": "cd",
      "flask-label": "system_u:system_r:hvm_guest_t",
      "disk": {
        "0": {
      "path": "\/storage\/disks\/",
          "type": "vhd","mode": "w",
          "device": "hda",
          "devtype": "disk",
          "shared": "true"
        }
      },
      "vcpus": "1",
      "qemu-dm-path": "\/usr\/sbin\/svirt-interpose"
    },
    "hidden": "true",
    "hidden-in-ui": "true"
  }
"""
LINUX_TEMPLATE="""{
  "type": "svm",
  "v4v-firewall-rules": {
    "0": "myself -> 0:4346709",
    "1": "myself -> 0:80",
    "2": "myself-if-seamless:14494 -> 0:4494",
    "3": "seamless -> myself-if-seamless:100",
    "4": "seamless:11494 -> myself-if-seamless:1494",
    "5": "myself -> 0:5556",
    "6": "my-stubdom -> 0:5555",
    "7": "my-stubdom -> 0:4001",
    "8": "my-stubdom -> 0:4002",
    "9": "my-stubdom -> 0:5000",
    "10": "my-stubdom -> 0:5001",
    "11": "my-stubdom -> 0:5559"
  },
  "description": "Linux (Debian, Ubuntu)",
  "os": "linux",
  "ui-selectable": "true",
  "xci-cpuid-signature": "true",
  "stubdom": "true",
  "image_path": "plugins\/vmimages\/notset_vm.png",
  "policies": {
    "audio-rec": "false"
  },
  "config": {
    "notify": "dbus",
    "hvm": "true",
    "pae": "true",
    "acpi": "true",
    "apic": "true",
    "viridian": "false",
    "hap": "true",
    "nx": "true",
    "v4v": "true",
    "sound": "ac97",
    "memory": "1024",
    "display": "none",
    "boot": "cd",
    "flask-label": "system_u:system_r:hvm_guest_t",
    "disk": {
      "0": {
        "path": "\/storage\/disks\/",
        "type": "file",
        "mode": "w",
        "device": "hda",
        "devtype": "disk",
        "shared": "true"
      },
      "1": {
        "path": "\/storage\/isos\/xc-tools.iso",
        "type": "file",
        "mode": "r",
        "device": "hdc",
        "devtype": "cdrom"
      }
    },
    "vcpus": "1",
    "qemu-dm-path": "\/usr\/sbin\/svirt-interpose"
  }
}
"""

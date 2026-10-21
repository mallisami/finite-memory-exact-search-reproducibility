# Local Infrastructure vs Public Reproducibility Artifact

## Local-only
Remove before public release:
- public/private IPs;
- SSH user;
- host aliases if identifying;
- ProxyJump config;
- Azure subscription/resource identifiers;
- K3s join token;
- SSH keys;
- credentials.

## Public scientific metadata
Retain:
- vCPU/RAM class;
- Azure VM SKU if non-identifying/appropriate;
- CPU model;
- OS/kernel;
- Python/package lock;
- thread caps;
- source/model/config hashes;
- machine-block design;
- case assignment rule;
- result and analysis artifacts.

No secrets are required for scientific reproduction.

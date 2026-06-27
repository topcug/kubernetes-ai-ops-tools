# Security Report: minikube

Generated: 2025-10-11 18:39:40

## RISK: HIGH

Immediate action required | Score: 400 | CRITICAL: 5 | HIGH: 70 | MEDIUM: 133 | LOW: 15

---

## WHAT TO DO (Top 5)

1. UPDATE IMAGE: storage-provisioner:v5
   Risk: 5 CRITICAL + 51 HIGH
   - stdlib -> 1.15.13, 1.16.5 (43 vulns)
   - golang.org/x/crypto -> latest (5 vulns)
   - golang.org/x/net -> latest (4 vulns)

2. UPDATE IMAGE: coredns:v1.12.1
   Risk: 0 CRITICAL + 5 HIGH
   - github.com/coredns/coredns -> 1.11.0 (2 vulns)
   - stdlib -> 1.24.4 (2 vulns)
   - github.com/quic-go/quic-go -> 0.49.1, 0.54.1 (1 vulns)

3. UPDATE IMAGE: kube-proxy:v1.34.0
   Risk: 0 CRITICAL + 1 HIGH
   - libc6 -> 2.36-9+deb12u11 (1 vulns)

4. UPDATE IMAGE: etcd:3.6.4-0
   Risk: 0 CRITICAL + 1 HIGH
   - stdlib -> 1.23.12, 1.24.6 (1 vulns)

5. FIX CLUSTER CONFIG
   14 HIGH/CRITICAL misconfigurations
   See 'Configuration Issues' section below

---

## CRITICAL Issues (5)

**CVE-2023-24538** | storage-provisioner:v5 | CVSS 9.8 | Found by: Grype, Trivy 🔒
- Package: stdlib (v1.16.2)
- Fix: Update to 1.19.8, 1.20.3
- Info: https://access.redhat.com/errata/RHSA-2023:6474

**CVE-2023-24540** | storage-provisioner:v5 | CVSS 9.8 | Found by: Grype, Trivy 🔒
- Package: stdlib (v1.16.2)
- Fix: Update to 1.19.9, 1.20.4
- Info: https://access.redhat.com/errata/RHSA-2023:6474

**CVE-2024-24790** | storage-provisioner:v5 | CVSS 9.8 | Found by: Grype, Trivy 🔒
- Package: stdlib (v1.16.2)
- Fix: Update to 1.21.11, 1.22.4
- Info: http://www.openwall.com/lists/oss-security/2024/06/04/1

**CVE-2022-23806** | storage-provisioner:v5 | CVSS 9.1 | Found by: Grype, Trivy 🔒
- Package: stdlib (v1.16.2)
- Fix: Update to 1.16.14, 1.17.7
- Info: https://access.redhat.com/security/cve/CVE-2022-23806

**CVE-2024-45337** | storage-provisioner:v5 | CVSS 0.0 | Found by: Trivy
- Package: golang.org/x/crypto (v0.0.0-20201002170205-7f63de1d35b0)
- Fix: Update to 0.31.0
- Info: http://www.openwall.com/lists/oss-security/2024/12/11/2

---

## HIGH Issues (70)

- **CVE-2022-30580** | storage-provisioner:v5 | stdlib -> 1.17.11, 1.18.3 | Found by: Grype, Trivy 🔒
- **CVE-2023-29403** | storage-provisioner:v5 | stdlib -> 1.19.10, 1.20.5 | Found by: Grype, Trivy 🔒
- **CVE-2022-2880** | storage-provisioner:v5 | stdlib -> 1.18.7, 1.19.2 | Found by: Grype, Trivy 🔒
- **CVE-2023-45283** | storage-provisioner:v5 | stdlib -> 1.20.11, 1.21.4, 1.20.12, 1.21.5 | Found by: Grype, Trivy 🔒
- **CVE-2023-45287** | storage-provisioner:v5 | stdlib -> 1.20.0 | Found by: Grype, Trivy 🔒
- **CVE-2022-30630** | storage-provisioner:v5 | stdlib -> 1.17.12, 1.18.4 | Found by: Grype, Trivy 🔒
- **CVE-2022-29804** | storage-provisioner:v5 | stdlib -> 1.17.11, 1.18.3 | Found by: Grype, Trivy 🔒
- **CVE-2023-39325** | storage-provisioner:v5 | golang.org/x/net -> 0.17.0 | Found by: Trivy
- **CVE-2023-28452** | coredns:v1.12.1 | github.com/coredns/coredns -> 1.11.0 | Found by: Trivy
- **CVE-2023-24537** | storage-provisioner:v5 | stdlib -> 1.19.8, 1.20.3 | Found by: Grype, Trivy 🔒

...and 60 more

---

## Configuration Issues

**HIGH** (14)
- 1.1.1: Ensure that the API server pod specification file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 1.1.13: Ensure that the default administrative credential file permissions are set to 600 (Automated) [Kube-bench]
- 1.1.15: Ensure that the scheduler.conf file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 1.1.17: Ensure that the controller-manager.conf file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 1.1.3: Ensure that the controller manager pod specification file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 1.1.5: Ensure that the scheduler pod specification file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 1.1.7: Ensure that the etcd pod specification file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 4.1.1: Ensure that the kubelet service file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 4.1.5: Ensure that the --kubeconfig kubelet.conf file permissions are set to 600 or more restrictive (Automated) [Kube-bench]
- 4.1.9: If the kubelet config.yaml configuration file is being used validate permissions set to 600 or more restrictive (Automated) [Kube-bench]
- C-0066: Secret/etcd encryption enabled [Kubescape]
- C-0067: Audit logs enabled [Kubescape]
- C-0068: PSP enabled [Kubescape]
- POP-1: [POP-100] Untagged docker image in use [Popeye]

**MEDIUM** (86)
- 1.1.11: Ensure that the etcd data directory permissions are set to 700 or more restrictive (Automated) [Kube-bench]
- 1.1.12: Ensure that the etcd data directory ownership is set to etcd:etcd (Automated) [Kube-bench]
- 1.1.14: Ensure that the default administrative credential file ownership is set to root:root (Automated) [Kube-bench]
- 1.1.16: Ensure that the scheduler.conf file ownership is set to root:root (Automated) [Kube-bench]
- 1.1.18: Ensure that the controller-manager.conf file ownership is set to root:root (Automated) [Kube-bench]
- 1.1.19: Ensure that the Kubernetes PKI directory and file ownership is set to root:root (Automated) [Kube-bench]
- 1.1.2: Ensure that the API server pod specification file ownership is set to root:root (Automated) [Kube-bench]
- 1.1.4: Ensure that the controller manager pod specification file ownership is set to root:root (Automated) [Kube-bench]
- 1.1.6: Ensure that the scheduler pod specification file ownership is set to root:root (Automated) [Kube-bench]
- 1.1.8: Ensure that the etcd pod specification file ownership is set to root:root (Automated) [Kube-bench]
- 1.2.15: Ensure that the --profiling argument is set to false (Automated) [Kube-bench]
- 1.2.16: Ensure that the --audit-log-path argument is set (Automated) [Kube-bench]
- 1.2.17: Ensure that the --audit-log-maxage argument is set to 30 or as appropriate (Automated) [Kube-bench]
- 1.2.18: Ensure that the --audit-log-maxbackup argument is set to 10 or as appropriate (Automated) [Kube-bench]
- 1.2.19: Ensure that the --audit-log-maxsize argument is set to 100 or as appropriate (Automated) [Kube-bench]
- 1.2.30: Ensure that the --service-account-extend-token-expiration parameter is set to false (Automated) [Kube-bench]
- 1.2.5: Ensure that the --kubelet-certificate-authority argument is set as appropriate (Automated) [Kube-bench]
- 1.3.2: Ensure that the --profiling argument is set to false (Automated) [Kube-bench]
- 1.4.1: Ensure that the --profiling argument is set to false (Automated) [Kube-bench]
- 4.1.10: If the kubelet config.yaml configuration file is being used validate file ownership is set to root:root (Automated) [Kube-bench]
- 4.1.6: Ensure that the --kubeconfig kubelet.conf file ownership is set to root:root (Automated) [Kube-bench]
- 4.2.1: Ensure that the --anonymous-auth argument is set to false (Automated) [Kube-bench]
- 4.2.2: Ensure that the --authorization-mode argument is not set to AlwaysAllow (Automated) [Kube-bench]
- 4.2.3: Ensure that the --client-ca-file argument is set as appropriate (Automated) [Kube-bench]
- C-0002: Prevent containers from allowing command execution [Kubescape]
- C-0013: Non-root containers [Kubescape]
- C-0016: Allow privilege escalation [Kubescape]
- C-0017: Immutable container filesystem [Kubescape]
- C-0030: Ingress and Egress blocked [Kubescape]
- C-0034: Automatic mapping of service account [Kubescape]
- C-0035: Administrative Roles [Kubescape]
- C-0044: Container hostPort [Kubescape]
- C-0055: Linux hardening [Kubescape]
- C-0270: Ensure CPU limits are set [Kubescape]
- C-0271: Ensure memory limits are set [Kubescape]
- POP-10: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-11: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-12: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-13: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]
- POP-14: [POP-107] No resource limits defined [Popeye]
- POP-15: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-16: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-17: [POP-307] Pod references a non existing ServiceAccount: "" [Popeye]
- POP-18: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-19: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]
- POP-2: [POP-106] No resources requests/limits defined [Popeye]
- POP-20: [POP-107] No resource limits defined [Popeye]
- POP-21: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-22: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-23: [POP-307] Pod references a non existing ServiceAccount: "" [Popeye]
- POP-24: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-25: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]
- POP-26: [POP-107] No resource limits defined [Popeye]
- POP-27: [POP-104] No readiness probe [Popeye]
- POP-28: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-29: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-3: [POP-102] No probes defined [Popeye]
- POP-30: [POP-307] Pod references a non existing ServiceAccount: "" [Popeye]
- POP-31: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-32: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]
- POP-33: [POP-106] No resources requests/limits defined [Popeye]
- POP-34: [POP-102] No probes defined [Popeye]
- POP-35: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-36: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-37: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-38: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]
- POP-39: [POP-107] No resource limits defined [Popeye]
- POP-4: [POP-208] Unmanaged pod detected. Best to use a controller [Popeye]
- POP-40: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-41: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-42: [POP-307] Pod references a non existing ServiceAccount: "" [Popeye]
- POP-43: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-44: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]
- POP-45: [POP-106] No resources requests/limits defined [Popeye]
- POP-46: [POP-102] No probes defined [Popeye]
- POP-47: [POP-208] Unmanaged pod detected. Best to use a controller [Popeye]
- POP-48: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-49: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-5: [POP-1204] Pod ingress is not secured by a network policy [Popeye]
- POP-50: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-51: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]
- POP-52: [POP-1109] Single endpoint is associated with this service [Popeye]
- POP-6: [POP-1204] Pod egress is not secured by a network policy [Popeye]
- POP-7: [POP-300] Uses "default" ServiceAccount [Popeye]
- POP-8: [POP-306] Container could be running as root user. Check SecurityContext/Image [Popeye]
- POP-9: [POP-302] Pod could be running as root user. Check SecurityContext/Image [Popeye]

---

Scanned: 9 images | Scanners: Grype, Kube-bench, Kubescape, Popeye, Trivy | High confidence: 99/162 vulns (found by 2+ scanners)

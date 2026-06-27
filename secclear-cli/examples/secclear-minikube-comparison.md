# Scanner Comparison Report: minikube

Generated: 2025-10-11 18:39:40

## WHAT TO DO

1. **Keep using all 5 scanners** - Each catches different problems
   - Grype: Finds CVEs in container images (138 total, 4 CRITICAL)
   - Trivy: Finds CVEs in container images (123 total, 5 CRITICAL)
   - Kube-bench: Finds cluster config problems (34 issues, 10 HIGH)
   - Kubescape: Finds cluster config problems (14 issues, 3 HIGH)
   - Popeye: Finds cluster config problems (52 issues, 1 HIGH)

2. **Fix high-confidence issues first** (99 vulns found by multiple scanners)

3. **Review single-scanner findings** (63 total - may include false positives)
   - Grype only: 39 vulns
   - Trivy only: 24 vulns

---

## Scanner Performance

**Grype:** 138 vulns (4 CRITICAL, 43 HIGH)
**Trivy:** 123 vulns (5 CRITICAL, 56 HIGH)

**Kube-bench:** 34 config issues (10 HIGH)
**Kubescape:** 14 config issues (3 HIGH)
**Popeye:** 52 config issues (1 HIGH)

**ACTION PLAN:**
1. Fix 99 high-confidence vulnerabilities (multiple scanners agree)
2. Review 63 single-scanner findings for false positives
3. Fix 14 HIGH cluster config issues

---

## Detailed Comparison (Image Scanners)

| Scanner | CRITICAL | HIGH | MEDIUM | LOW | TOTAL | Unique |
|---------|----------|------|--------|-----|-------|--------|
| Grype | 4 | 43 | 37 | 15 | 138 | 39 |
| Trivy | 5 | 56 | 47 | 15 | 123 | 24 |

**Agreement:** 99 vulns found by 2+ scanners (61%)

## Cluster Scanners

| Scanner | HIGH | MEDIUM | LOW | TOTAL |
|---------|------|--------|-----|-------|
| Kube-bench | 10 | 24 | 0 | 34 |
| Kubescape | 3 | 11 | 0 | 14 |
| Popeye | 1 | 51 | 0 | 52 |


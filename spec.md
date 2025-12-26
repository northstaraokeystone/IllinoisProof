# IllinoisProof Specification v1.0

## Overview

IllinoisProof is a receipts-native fraud detection and accountability infrastructure targeting three documented corruption tiers in Illinois:

| Tier | Case | Dollar Value | Detection Challenge |
|------|------|--------------|---------------------|
| LOCAL | Henyard/Dolton | $3.65M deficit, $779K unexplained | Cascade: credit card → deficit → vendor |
| SYSTEMIC | IDES Pandemic | $5.24B overpayments | Identity theft: prison/deceased crossmatch |
| INSTITUTIONAL | Madigan/ComEd | $200M DPA fine | Pay-to-play network entropy |

## Inputs

### Tier 1: Local Government (Dolton/Cook County)
| Source | Access Method | Data Available | Key Fields |
|--------|---------------|----------------|------------|
| Illinois Comptroller Warehouse | Bulk download | 9,200+ annual financial reports FY2000-2024 | revenues, expenditures, fund_balances, debt |
| Cook County Open Data | Socrata REST API | Property, budget, court records | varies by dataset |
| AG Public Access Counselor | FOIA tracking | 3,500 complaints/year | request_date, response, denial_reason |
| PACER/CourtListener | REST API | 500M federal court documents | case_number, filings, parties |

### Tier 2: IDES Pandemic Fraud
| Source | Access Method | Data Available | Key Fields |
|--------|---------------|----------------|------------|
| IDES UI Dashboard | Web scraping | Aggregate claims, payments | weekly_claims, payments_total |
| DOL ETA 227 Reports | Quarterly federal | State-level UI statistics | overpayments, recovery_rate |
| Auditor General Reports | PDF extraction | Methodology, findings | sample_size, error_rate |

### Tier 3: Madigan/ComEd Institutional
| Source | Access Method | Data Available | Key Fields |
|--------|---------------|----------------|------------|
| Illinois Sunshine | REST API | 2.3M+ contributions since 1994 | committee_id, contributor, amount, date |
| ILGA Bill Status | Web scraping | Voting records since 1999 | bill_number, vote_date, members |
| PACER (Madigan Case) | CourtListener API | Trial exhibits, DPA docs | exhibit_id, content |

## Outputs

### Receipt Types
| Receipt Type | Module | Key Fields |
|--------------|--------|------------|
| ingest_receipt | ingest/*.py | source, records_count, hash |
| benford_receipt | detect/benford.py | chi_squared, p_value, pass_fail |
| entropy_receipt | detect/entropy.py | compression_ratio, z_score, is_anomaly |
| network_receipt | detect/network.py | nodes, edges, entropy, hubs |
| tier1_receipt | tier1_dolton/*.py | finding_type, severity, evidence_hash |
| tier2_receipt | tier2_ides/*.py | finding_type, dollar_value, recovery_status |
| tier3_receipt | tier3_madigan/*.py | finding_type, network_path, confidence |
| citizen_receipt | output/citizen.py | tweet_text, dashboard_id |
| fbi_receipt | output/fbi.py | package_id, custody_entries, package_hash |
| auditor_receipt | output/auditor.py | finding_id, materiality, recommendation |
| simulation_receipt | sim.py | cycle_id, accuracy_metrics, violations |

### Dual Output Formats
1. **Citizen-facing**: Tweet-ready, dashboard-friendly summaries
2. **FBI-grade**: NIST IR 8387 chain-of-custody, prosecution-ready evidence packages

## SLOs (Service Level Objectives)

| SLO | Threshold | Test Assertion | Stoprule Action |
|-----|-----------|----------------|-----------------|
| Benford p-value | < 0.05 to flag | assert p_value < 0.05 | emit finding_receipt |
| Compression z-score | > 2.0 to flag | assert z_score > 2.0 | emit anomaly_receipt |
| Network hub threshold | centrality > 0.3 | assert centrality > 0.3 | flag for investigation |
| Detection precision | >= 0.85 | assert precision >= 0.85 | review methodology |
| Detection recall | >= 0.90 | assert recall >= 0.90 | adjust thresholds |
| Calibration match | >= 95% of known | assert match >= 0.95 | calibration failure |
| Receipt emission | 100% of operations | assert all_receipts_present | HALT |
| Evidence integrity | hash match | assert hash_verified | HALT + alert |

## Stoprules

### Critical Halts
- Receipt emission failure: HALT immediately
- Evidence integrity violation: HALT + alert
- Calibration match < 95%: Review and halt

### Investigation Triggers
- Benford p-value < 0.05: Emit finding, continue
- Compression z-score > 2.0: Emit anomaly, continue
- Network centrality > 0.3: Flag hub, continue

### Escalation
- Detection precision < 0.85: Human review required
- Detection recall < 0.90: Threshold adjustment required

## Rollback Procedures

1. **Data Rollback**: Restore from last verified merkle anchor
2. **Analysis Rollback**: Re-run detection from last known-good state
3. **Evidence Rollback**: Never - evidence packages are immutable

## Detection Methods

### Benford's Law Analysis
- First-digit distribution: P(d) = log10(1 + 1/d)
- Expected frequencies: 1=30.1%, 2=17.6%, 3=12.5%, ...
- Chi-squared test for conformity
- 2BL-test (second digit) most sensitive for fraud

### Compression-Based Anomaly Detection
- Kolmogorov complexity via compression ratio
- NCD (Normalized Compression Distance) for comparison
- Higher entropy = more anomalous
- Flag outliers beyond 2 standard deviations

### Monte Carlo Simulation
- Generate probability distributions for fraud likelihood
- Inject known fraud patterns at varying rates
- Compute confidence intervals on findings

## Timeline Gates

### T+2h: SKELETON
- [ ] spec.md exists
- [ ] ledger_schema.json exists
- [ ] cli.py emits valid receipt JSON
- [ ] core.py has dual_hash, emit_receipt, merkle, StopRule

### T+24h: MVP
- [ ] All ingest modules fetch sample data
- [ ] Benford + entropy detection functional
- [ ] 10-cycle smoke test passes
- [ ] pytest coverage > 80%

### T+48h: HARDENED
- [ ] All 6 scenarios pass
- [ ] Calibration >= 95% match
- [ ] FBI-grade packaging functional
- [ ] Citizen dashboard output generates
- [ ] SHIP IT

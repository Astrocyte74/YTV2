# (Legacy) YTV2 PostgreSQL Migration Cutover Plan

## Overview
This document outlines the complete cutover strategy for migrating YTV2 from dual-SQLite architecture to PostgreSQL, including rollback procedures.

## Current Status (Phase 2 Complete)
✅ **PostgreSQL System Verified Ready**
- 81 content records imported and verified
- All API endpoints functional with identical responses to SQLite production
- Performance comparable to SQLite (avg difference: 14ms, PostgreSQL faster 67% of time)
- Regression shield endpoint `/health/backend` deployed for quick diagnostics

## Pre-Cutover Checklist

### 1. Data Verification
- [ ] Run final API parity test: `python test_api_parity.py`
- [ ] Verify PostgreSQL record count matches expected: `curl https://ytv2-dashboard-postgres.onrender.com/health/backend`
- [ ] Test key user journeys on PostgreSQL deployment
- [ ] Backup current SQLite database for rollback

### 2. DNS and Infrastructure
- [ ] PostgreSQL deployment health confirmed: https://ytv2-dashboard-postgres.onrender.com
- [ ] Current production confirmed: https://ytv2-vy9k.onrender.com
- [ ] Custom domain ready for switch (if applicable)

### 3. Monitoring Preparation
- [ ] Set up alerts for the cutover window
- [ ] Prepare latency monitoring: `python latency_monitor.py --mode continuous --duration 15`
- [ ] Alert stakeholders of cutover window

## Cutover Execution Plan

### Phase 3A: DNS Cutover (Recommended Method)
**Estimated downtime: 0-5 minutes (DNS propagation)**

```bash
# 1. Verify PostgreSQL system health
curl -s "https://ytv2-dashboard-postgres.onrender.com/health/backend" | jq .

# 2. Update DNS or domain routing
# Point ytv2.example.com → ytv2-dashboard-postgres.onrender.com
# (Specific steps depend on DNS provider)

# 3. Verify cutover
curl -s "https://[YOUR-DOMAIN]/health/backend" | jq .
# Should show: "backend": "PostgreSQLContentIndex"

# 4. Monitor for 15 minutes
python latency_monitor.py --mode continuous --duration 15
```

### Phase 3B: Render Service Swap (Alternative Method)
**Estimated downtime: 2-10 minutes**

```bash
# 1. Clone PostgreSQL app as new service
# 2. Swap the custom domain from old to new service
# 3. Verify health endpoint shows PostgreSQL
# 4. Delete old SQLite service (after verification period)
```

## Rollback Procedures

### Immediate Rollback (Within 1 Hour)
If issues detected immediately after cutover:

```bash
# Method A: DNS Rollback (if using DNS cutover)
# 1. Revert DNS changes
# Point domain back to: ytv2-vy9k.onrender.com

# Method B: Service Rollback (if using service swap)
# 1. Re-attach domain to original SQLite service
# 2. Verify: curl https://[YOUR-DOMAIN]/health/backend
#    Should return 404 (confirming SQLite backend)
```

### Extended Rollback (Up to 24 Hours)
If issues discovered later:

```bash
# 1. Emergency DNS switch back to SQLite
# Point domain → ytv2-vy9k.onrender.com

# 2. Investigate PostgreSQL issues
# Check logs: Render dashboard → ytv2-dashboard-postgres → Logs

# 3. Preserve data integrity
# Run data export from PostgreSQL if any new data was created

# 4. Plan fix and re-cutover
```

## Post-Cutover Verification

### Immediate Verification (First 15 minutes)
```bash
# 1. Verify backend type
curl -s "https://[YOUR-DOMAIN]/health/backend" | jq .backend
# Expected: "PostgreSQLContentIndex"

# 2. Test API endpoints
python test_api_parity.py

# 3. Verify key functionality
curl -s "https://[YOUR-DOMAIN]/api/reports?size=3" | jq '.reports | length'
# Expected: 3

# 4. Test dashboard UI
# Visit https://[YOUR-DOMAIN] and verify:
# - Cards load correctly
# - Filters work
# - Individual reports display
# - Audio playback functions
```

### Extended Verification (First 24 hours)
- [ ] Monitor latency trends with `latency_monitor.py`
- [ ] Check error rates in Render logs
- [ ] Verify all user-facing features work
- [ ] Monitor for any data consistency issues
- [ ] Check with key users about performance

## Rollback Decision Matrix

| Issue Type | Severity | Action | Timeframe |
|------------|----------|--------|-----------|
| Complete outage | Critical | Immediate DNS rollback | < 5 minutes |
| API errors 50%+ | High | Immediate rollback | < 15 minutes |
| Performance degradation 2x+ | High | Immediate rollback | < 30 minutes |
| UI rendering issues | Medium | Investigate, rollback if no quick fix | < 1 hour |
| Minor data inconsistency | Low | Monitor, fix in PostgreSQL | 24 hours |

## Environment Variables Check

### PostgreSQL Deployment Required Settings
```bash
# Production environment variables for PostgreSQL system:
READ_FROM_POSTGRES=true
DATABASE_URL_POSTGRES_NEW=[PostgreSQL connection string]
SYNC_SECRET=[secure sync token]
PORT=10000
```

### Verification Commands
```bash
# Check environment configuration
curl -s "https://ytv2-dashboard-postgres.onrender.com/health/backend" | jq '{
  backend: .backend,
  read_from_postgres: .read_from_postgres,
  dsn_set: .dsn_set,
  record_count: .record_count
}'

# Expected output:
# {
#   "backend": "PostgreSQLContentIndex",
#   "read_from_postgres": true,
#   "dsn_set": true,
#   "record_count": 81
# }
```

## Success Criteria

### Cutover is considered successful when:
1. ✅ `/health/backend` shows `PostgreSQLContentIndex` backend
2. ✅ API parity tests pass 100%
3. ✅ Dashboard UI functions normally
4. ✅ Performance within 50ms of SQLite baseline
5. ✅ No errors in application logs for 30 minutes
6. ✅ User functionality verified by stakeholders

### PostgreSQL migration is complete when:
1. ✅ Cutover successful for 24 hours
2. ✅ All monitoring shows stable performance
3. ✅ SQLite deployment can be safely decommissioned
4. ✅ Documentation updated to reflect new architecture

## Emergency Contacts

### Technical Issues
- Primary: Check Render dashboard logs
- Secondary: Use `/health/backend` endpoint for quick diagnosis
- Escalation: Review this document's rollback procedures

### Communication Plan
- Notify stakeholders of cutover start time
- Provide status updates every 15 minutes during cutover window
- Send completion confirmation with health check results

## Risk Mitigation

### Data Loss Prevention
- PostgreSQL database includes all 81 records from SQLite
- Original SQLite backup preserved until 7 days post-cutover
- Sync functionality maintained for emergency data transfer

### Performance Monitoring
- Latency baseline established: SQLite ~147ms, PostgreSQL ~161ms
- Acceptable performance range: < 300ms for health endpoints
- Automatic rollback if performance degrades beyond 2x baseline

## Testing Schedule

### Pre-Cutover Testing (Complete)
- ✅ API parity tests confirm identical functionality
- ✅ Performance baseline established
- ✅ Regression shield endpoint deployed
- ✅ Rollback procedures documented and verified

### Go/No-Go Decision Criteria
**GO** if all criteria met:
- [ ] API parity tests pass 100%
- [ ] PostgreSQL system healthy for 24+ hours
- [ ] Performance within acceptable range
- [ ] Rollback procedures tested and confirmed
- [ ] Stakeholder approval received

**NO-GO** if any critical issue:
- [ ] API parity tests fail
- [ ] PostgreSQL system instability
- [ ] Performance unacceptable (>2x baseline)
- [ ] Rollback procedures untested
- [ ] Resource constraints

---

**Document Version**: 1.0
**Last Updated**: 2025-09-18
**Migration Phase**: Phase 2 Complete, Ready for Phase 3 Cutover

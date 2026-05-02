"""
Watchdog Agent
Proactively monitors documents and surfaces alerts without being asked.
Runs on a schedule via Celery background tasks.
"""
import json
import logging
from typing import Annotated, List
from datetime import datetime, timedelta
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)


class WatchdogAgent:
    """
    The Watchdog runs silently in the background, watching for things 
    that need attention. It checks for contract expirations, complaint 
    spikes, policy conflicts, and regulatory deadlines — then surfaces 
    them as alerts in the dashboard.
    """

    @kernel_function(
        description="""Run all proactive monitoring checks and return a list of alerts.
        Use this to get a full picture of what needs attention right now."""
    )
    async def run_all_checks(
        self,
        organisation: Annotated[str, "Organisation name to check"] = "MTN Nigeria",
    ) -> str:
        """Run every watchdog check and aggregate results."""
        all_alerts = []

        try:
            contracts = json.loads(await self.check_contract_expiry(organisation))
            all_alerts.extend(contracts.get("alerts", []))
        except Exception as e:
            logger.warning(f"Contract check failed: {e}")

        try:
            complaints = json.loads(await self.detect_complaint_spike(organisation))
            all_alerts.extend(complaints.get("alerts", []))
        except Exception as e:
            logger.warning(f"Complaint check failed: {e}")

        try:
            conflicts = json.loads(await self.find_policy_conflicts(organisation))
            all_alerts.extend(conflicts.get("alerts", []))
        except Exception as e:
            logger.warning(f"Policy check failed: {e}")

        try:
            regulatory = json.loads(await self.check_regulatory_deadlines(organisation))
            all_alerts.extend(regulatory.get("alerts", []))
        except Exception as e:
            logger.warning(f"Regulatory check failed: {e}")

        critical = [a for a in all_alerts if a.get("severity") == "critical"]
        warnings = [a for a in all_alerts if a.get("severity") == "warning"]

        return json.dumps({
            "total_alerts": len(all_alerts),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "alerts": all_alerts,
            "checked_at": datetime.utcnow().isoformat(),
        })

    @kernel_function(
        description="""Check for contracts expiring within the next 90 days.
        Returns a list of alerts for contracts needing renewal attention."""
    )
    async def check_contract_expiry(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
        days_ahead: Annotated[int, "How many days ahead to check"] = 90,
    ) -> str:
        # In production: queries Azure Search for documents where
        # doc_type=contract and expiry_date < now + days_ahead
        # For demo: returns realistic MTN contracts
        alerts = [
            {
                "alert_type": "contract_expiry",
                "severity": "critical",
                "title": "TowerCo Infrastructure Contract Expiring in 14 Days",
                "summary": (
                    "The TowerCo Nigeria infrastructure agreement (₦45M/month) expires on "
                    "May 15, 2026. Renewal notice was required 90 days ago. Immediate action needed."
                ),
                "metadata": {
                    "contract_title": "TowerCo Nigeria Infrastructure Agreement",
                    "expiry_date": "2026-05-15",
                    "monthly_value": 45000000,
                    "days_remaining": 14,
                    "document_id": "doc_002",
                },
                "suggested_actions": [
                    "Contact TowerCo Nigeria procurement team immediately",
                    "Review current SLA performance before negotiating renewal terms",
                    "Prepare renewal or termination notice this week",
                    "Loop in legal team for contract review",
                ],
            },
            {
                "alert_type": "contract_expiry",
                "severity": "warning",
                "title": "Ericsson Maintenance Agreement Expiring in 45 Days",
                "summary": (
                    "The Ericsson equipment maintenance contract expires June 16, 2026. "
                    "Begin renewal discussions to avoid service gap."
                ),
                "metadata": {
                    "contract_title": "Ericsson Equipment Maintenance SLA",
                    "expiry_date": "2026-06-16",
                    "monthly_value": 12000000,
                    "days_remaining": 45,
                    "document_id": "doc_007",
                },
                "suggested_actions": [
                    "Schedule renewal meeting with Ericsson account manager",
                    "Review equipment maintenance history before renewal",
                ],
            },
        ]

        return json.dumps({"check": "contract_expiry", "alerts": alerts})

    @kernel_function(
        description="""Detect unusual spikes in customer complaints compared to the 
        historical baseline. Returns an alert if complaints have increased significantly."""
    )
    async def detect_complaint_spike(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
        threshold_pct: Annotated[float, "Percentage increase considered a spike"] = 40.0,
    ) -> str:
        # In production: queries complaint database and computes rolling average
        # For demo: returns a live-looking spike alert
        alerts = [
            {
                "alert_type": "complaint_spike",
                "severity": "critical",
                "title": "Customer Complaint Spike — Lagos Zone 7 (+187%)",
                "summary": (
                    "Customer complaints in Lagos Zone 7 have increased 187% in the last 24 hours "
                    "(47 tickets vs daily average of 16). Most affected area: Ikeja. "
                    "Peak time: 6pm-9pm. Primary complaint: slow data speeds."
                ),
                "metadata": {
                    "region": "Lagos Zone 7",
                    "current_24h": 47,
                    "historical_daily_avg": 16,
                    "increase_pct": 187,
                    "top_complaint": "slow data speeds",
                    "peak_hours": "18:00-21:00",
                    "affected_area": "Ikeja",
                },
                "suggested_actions": [
                    "Investigate Tower 4471 in Ikeja — known intermittent failure history",
                    "Check network capacity utilisation for Lagos Zone 7",
                    "Cross-reference with competitor promotions driving traffic shifts",
                    "Prepare customer apology communication",
                    "Escalate to Network Operations for emergency review",
                ],
            }
        ]

        return json.dumps({"check": "complaint_spike", "alerts": alerts})

    @kernel_function(
        description="""Check for conflicts between internal policies and new regulations.
        Returns alerts where policy documents contradict regulatory requirements."""
    )
    async def find_policy_conflicts(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
    ) -> str:
        alerts = [
            {
                "alert_type": "policy_conflict",
                "severity": "warning",
                "title": "NCC Regulation Conflicts With Data Retention Policy",
                "summary": (
                    "The new NCC Consumer Protection Regulation (March 2026) requires customer "
                    "data retention for 7 years. MTN Data Retention Policy v3.2 specifies 5 years. "
                    "Section 4.2 of the internal policy must be updated."
                ),
                "metadata": {
                    "regulation": "NCC Consumer Protection Regulation 2026",
                    "internal_policy": "MTN Data Retention Policy v3.2",
                    "conflict_section": "Section 4.2 — Data Retention Duration",
                    "regulation_requirement": "7 years",
                    "current_policy": "5 years",
                },
                "suggested_actions": [
                    "Update Data Retention Policy section 4.2 to reflect 7-year requirement",
                    "Submit updated policy to Legal for review and approval",
                    "Notify IT to extend data retention infrastructure accordingly",
                    "Document the change for NCC compliance audit trail",
                ],
            }
        ]

        return json.dumps({"check": "policy_conflicts", "alerts": alerts})

    @kernel_function(
        description="""Check for upcoming regulatory submission deadlines.
        Returns alerts for any NCC or government filings due within 30 days."""
    )
    async def check_regulatory_deadlines(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
    ) -> str:
        alerts = [
            {
                "alert_type": "regulatory_deadline",
                "severity": "warning",
                "title": "NCC QoS Report Due in 12 Days",
                "summary": (
                    "The quarterly Quality of Service report to NCC is due May 13, 2026. "
                    "Previous submission: February 2026. Report requires network uptime, "
                    "complaint resolution rates, and coverage statistics."
                ),
                "metadata": {
                    "filing": "NCC QoS Quarterly Report",
                    "due_date": "2026-05-13",
                    "days_remaining": 12,
                    "last_submitted": "2026-02-13",
                },
                "suggested_actions": [
                    "Begin compiling Q1 2026 network performance data",
                    "Request complaint resolution statistics from Customer Experience",
                    "Assign report owner and set internal deadline for May 10",
                ],
            }
        ]

        return json.dumps({"check": "regulatory_deadlines", "alerts": alerts})

    @kernel_function(
        description="""Check external factors that might explain internal patterns.
        Use this when investigating the root cause of complaints or performance drops."""
    )
    async def check_external_factors(
        self,
        region: Annotated[str, "Geographic region to check"] = "Lagos",
        date_range: Annotated[str, "Date range to check e.g. '7d', '30d'"] = "7d",
    ) -> str:
        # In production: could check news APIs, competitor announcements, etc.
        # For demo: returns realistic competitive intelligence
        return json.dumps({
            "region": region,
            "date_range": date_range,
            "external_factors": [
                {
                    "factor": "Competitor Promotion",
                    "description": (
                        "Glo launched a 10GB for ₦500 data promotion on April 27, 2026 "
                        "targeting Lagos subscribers. This likely caused a 12-15% traffic "
                        "shift to MTN from customers sharing hotspots, increasing load."
                    ),
                    "impact": "high",
                    "started": "2026-04-27",
                },
                {
                    "factor": "Public Holiday Traffic",
                    "description": "Workers Day (May 1) led to increased residential data usage.",
                    "impact": "medium",
                    "started": "2026-05-01",
                },
            ],
            "conclusion": (
                "The combination of competitor promotion driving traffic shifts and "
                "holiday residential usage likely contributed to Lagos Zone 7 congestion."
            ),
        })

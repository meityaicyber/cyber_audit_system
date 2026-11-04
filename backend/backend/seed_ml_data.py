import asyncio
import uuid
import random
from datetime import datetime, timedelta, timezone
import sys
import os

# Ensure app is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal
from app.models.agency import Agency
from app.models.report import Report, ReportsData, DetailedObservation, ObservationSeverity, ObservationStatus, UploadStatus
from app.models.user import User, Role, UserRole, UserSession
from app.models.audit import AuditLog, SecurityEvent

async def seed_data():
    async with AsyncSessionLocal() as db:
        print("Starting seed...")

        # Create Agencies
        agencies = []
        for i in range(1, 51):
            agency = Agency(
                agency_id=uuid.uuid4(),
                agency_code=f"AG-SEED-{i:03d}-{random.randint(1000,9999)}",
                agency_name=f"Mock Agency {i}",
                agency_type=random.choice(['CERT_IN_EMPANELLED', 'PRIVATE_AUDITOR', 'INTERNAL_AUDIT_TEAM']),
                contact_person="John Doe",
                contact_email=f"contact{i}@mock.com",
            )
            db.add(agency)
            agencies.append(agency)
        await db.commit()
        
        # We need historical data for forecasting (at least 12 months)
        now = datetime.now(timezone.utc)
        
        for i in range(5000): # 5000 reports with a spike in recent months
            if random.random() < 0.5:
                days_ago = random.randint(1, 60) # Spike in the last 60 days
            else:
                days_ago = random.randint(61, 365)
            report_time = now - timedelta(days=days_ago)
            agency = random.choice(agencies)
            
            report_id = uuid.uuid4()
            report = Report(
                report_id=report_id,
                original_filename=f"audit_report_{i}.pdf",
                stored_filename=f"enc_{uuid.uuid4()}.pdf",
                file_extension=".pdf",
                mime_type="application/pdf",
                file_size=random.randint(100000, 5000000),
                sha256_hash=uuid.uuid4().hex,
                upload_status=UploadStatus.VALIDATED,
                agency_id=agency.agency_id,
                created_at=report_time,
                updated_at=report_time
            )
            db.add(report)
            
            rd = ReportsData(
                report_id=report_id,
                report_date=report_time.date(),
                data={"mock": "data"}
            )
            db.add(rd)
            
            # Generate 5 to 25 vulnerabilities per report
            num_vulns = random.randint(5, 25)
            for v_idx in range(num_vulns):
                # 40% chance of critical/high score
                if random.random() < 0.4:
                    cvss = round(random.uniform(7.0, 10.0), 1)
                else:
                    cvss = round(random.uniform(2.0, 6.9), 1)
                
                if cvss >= 9.0:
                    sev = ObservationSeverity.Critical
                elif cvss >= 7.0:
                    sev = ObservationSeverity.High
                elif cvss >= 4.0:
                    sev = ObservationSeverity.Medium
                else:
                    sev = ObservationSeverity.Low
                    
                vuln = DetailedObservation(
                    finding_id=uuid.uuid4(),
                    report_id=report_id,
                    title=f"Mock DetailedObservation {v_idx} for Report {i}",
                    severity=sev,
                    cvss_score=cvss,
                    status=random.choice(list(ObservationStatus)),
                    created_at=report_time,
                    updated_at=report_time
                )
                db.add(vuln)
                
        await db.commit()
        print("Seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())

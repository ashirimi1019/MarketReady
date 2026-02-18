from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.entities import (
    Major,
    CareerPathway,
    MajorPathwayMap,
    Skill,
    ChecklistVersion,
    ChecklistItem,
    Milestone,
)


CHECKLISTS = {
    "Software Engineer (Full-Stack, Cloud-Ready)": {
        "non_negotiable": [
            ("Git & GitHub", ["repo_url"], False),
            ("Backend language (Java or Python)", ["repo_url"], False),
            ("REST APIs + databases", ["repo_url", "architecture_diagram"], False),
            ("SQL fundamentals", ["lab_report", "writeup"], False),
            ("Linux basics", ["lab_report"], False),
            ("Cloud fundamentals (AWS/GCP)", ["writeup"], False),
            ("Deployed full-stack application", ["deployed_url", "repo_url"], True),
        ],
        "strong_signal": [
            ("Docker", ["repo_url"], False),
            ("CI/CD pipelines", ["repo_url"], False),
            ("Authentication & authorization", ["repo_url"], False),
            ("AWS certification or equivalent project", ["cert_upload", "repo_url"], False),
            ("Basic system design reasoning", ["writeup", "architecture_diagram"], False),
        ],
    },
    "Data Analyst (SQL, BI, Cloud-Ready)": {
        "non_negotiable": [
            ("Advanced SQL", ["lab_report", "writeup"], False),
            ("Excel / Sheets", ["writeup"], False),
            ("Python (pandas) or R", ["repo_url"], False),
            ("BI dashboards", ["dashboard_link"], False),
            ("Data storytelling", ["writeup"], False),
            ("End-to-end analytics project", ["repo_url", "dashboard_link", "writeup"], True),
        ],
        "strong_signal": [
            ("Cloud warehouses", ["writeup"], False),
            ("ETL pipelines", ["repo_url"], False),
            ("Data modeling", ["writeup"], False),
        ],
    },
    "Cybersecurity Analyst (Cloud & SOC Fundamentals)": {
        "non_negotiable": [
            ("Networking fundamentals", ["lab_report"], False),
            ("Linux basics", ["lab_report"], False),
            ("Security principles", ["writeup"], False),
            ("Logging & monitoring", ["lab_report"], False),
            ("Home lab with documented exercises", ["lab_report", "writeup"], True),
        ],
        "strong_signal": [
            ("Security+", ["cert_upload"], False),
            ("Cloud IAM", ["writeup"], False),
            ("Incident response fundamentals", ["writeup", "lab_report"], False),
        ],
    },
}


MILESTONES = [
    (1, "Year 1: Foundations", "Core fundamentals and baseline skills."),
    (2, "Year 2: Core Build", "Structured projects to prove core skills."),
    (3, "Year 3: Proof Projects", "End-to-end proofs and portfolio artifacts."),
    (4, "Year 4: Market Readiness", "Finalize proofs and close readiness gaps."),
]


def get_or_create(session: Session, model, defaults=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    session.add(instance)
    session.flush()
    return instance


def ensure_checklist_item(session: Session, version_id, skill_id, title, tier, allowed_proof_types, is_critical):
    existing = (
        session.query(ChecklistItem)
        .filter(ChecklistItem.version_id == version_id)
        .filter(ChecklistItem.title == title)
        .one_or_none()
    )
    if existing:
        return existing
    item = ChecklistItem(
        version_id=version_id,
        skill_id=skill_id,
        title=title,
        tier=tier,
        allowed_proof_types=allowed_proof_types,
        is_critical=is_critical,
    )
    session.add(item)
    session.flush()
    return item


def ensure_milestones(session: Session, pathway_id):
    for semester_index, title, description in MILESTONES:
        existing = (
            session.query(Milestone)
            .filter(Milestone.pathway_id == pathway_id)
            .filter(Milestone.semester_index == semester_index)
            .one_or_none()
        )
        if existing:
            continue
        session.add(
            Milestone(
                pathway_id=pathway_id,
                title=title,
                description=description,
                semester_index=semester_index,
            )
        )
    session.flush()


def seed():
    session = SessionLocal()
    try:
        major = get_or_create(
            session,
            Major,
            name="Computer Science",
            defaults={"description": "Initial launch major"},
        )

        pathways = {}
        for name in CHECKLISTS.keys():
            pathways[name] = get_or_create(
                session,
                CareerPathway,
                name=name,
                defaults={"description": ""},
            )

        for pathway in pathways.values():
            get_or_create(
                session,
                MajorPathwayMap,
                major_id=major.id,
                pathway_id=pathway.id,
                defaults={"is_compatible": True, "notes": None},
            )

        for pathway_name, definitions in CHECKLISTS.items():
            pathway = pathways[pathway_name]

            version = (
                session.query(ChecklistVersion)
                .filter(ChecklistVersion.pathway_id == pathway.id)
                .filter(ChecklistVersion.version_number == 1)
                .one_or_none()
            )
            if not version:
                version = ChecklistVersion(
                    pathway_id=pathway.id,
                    version_number=1,
                    status="published",
                    published_at=datetime.utcnow(),
                )
                session.add(version)
                session.flush()

            for tier, items in definitions.items():
                for title, proof_types, is_critical in items:
                    skill = get_or_create(session, Skill, name=title, defaults={"description": None})
                    ensure_checklist_item(
                        session,
                        version_id=version.id,
                        skill_id=skill.id,
                        title=title,
                        tier=tier,
                        allowed_proof_types=proof_types,
                        is_critical=is_critical,
                    )

            ensure_milestones(session, pathway.id)

        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    seed()

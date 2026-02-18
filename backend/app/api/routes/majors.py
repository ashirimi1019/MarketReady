from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.api import MajorOut, PathwayWithCompatibility
from app.models.entities import Major, MajorPathwayMap, CareerPathway

router = APIRouter(prefix="/majors")


@router.get("", response_model=list[MajorOut])
def list_majors(db: Session = Depends(get_db)):
    return db.query(Major).filter(Major.is_active.is_(True)).all()


@router.get("/{major_id}/pathways", response_model=list[PathwayWithCompatibility])
def list_pathways_for_major(major_id: str, db: Session = Depends(get_db)):
    maps = (
        db.query(MajorPathwayMap)
        .filter(MajorPathwayMap.major_id == major_id)
        .all()
    )
    results = []
    for m in maps:
        pathway = db.query(CareerPathway).get(m.pathway_id)
        if pathway is None:
            continue
        results.append(
            {
                "id": pathway.id,
                "name": pathway.name,
                "description": pathway.description,
                "is_compatible": m.is_compatible,
                "notes": m.notes,
            }
        )
    return results

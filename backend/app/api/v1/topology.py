from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database.session import get_db
from app.models import NetworkLink
from app.schemas import NetworkLinkResponse
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine

router = APIRouter(prefix="/topology", tags=["Topology"])

@router.get("", response_model=Dict[str, Any])
def get_topology(db: Session = Depends(get_db)):
    """
    Returns nodes and edges formatted for React Flow.
    """
    return DigitalTwinEngine.get_topology_payload(db)

@router.get("/links", response_model=List[NetworkLinkResponse])
def get_links(db: Session = Depends(get_db)):
    return db.query(NetworkLink).all()

@router.get("/dependencies")
def get_dependencies(db: Session = Depends(get_db)):
    links = db.query(NetworkLink).all()
    deps = []
    for l in links:
        deps.append({
            "link": l.name,
            "type": l.link_type,
            "source": l.source_device_id,
            "target": l.target_device_id,
            "redundant": l.is_redundant
        })
    return {"dependencies": deps}

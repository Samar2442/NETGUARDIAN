from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models import Route
from app.schemas import RouteResponse

router = APIRouter(prefix="/routes", tags=["Routes"])

@router.get("", response_model=List[RouteResponse])
def get_routes(device_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Route)
    if device_id:
        query = query.filter(Route.device_id == device_id)
    return query.all()

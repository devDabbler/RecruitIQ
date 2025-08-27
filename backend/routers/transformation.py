from fastapi import APIRouter, HTTPException
from backend.models.transformation import (
    ATSConnectionRequest, DataAssessmentRequest, DataTransformationRequest
)
from backend.services.transformation_service import TransformationService

router = APIRouter(prefix="/transformation", tags=["Transformation"])
service = TransformationService()

@router.post("/connect")
async def connect_to_ats(connection_details: ATSConnectionRequest):
    try:
        return service.connect_to_ats(connection_details.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/assess")
async def assess_data_quality(assessment_request: DataAssessmentRequest):
    try:
        return service.assess_data_quality(assessment_request.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transform")
async def transform_data(transformation_request: DataTransformationRequest):
    try:
        return service.transform_data(transformation_request.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

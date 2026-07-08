from pydantic import BaseModel, ConfigDict


class DistrictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    district_id: int
    district_name: str
    latitude: float
    longitude: float

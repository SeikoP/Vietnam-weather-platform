from pydantic import BaseModel, ConfigDict


class ProvinceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    province_id: int
    province_name: str
    latitude: float
    longitude: float

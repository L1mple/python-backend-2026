from pydantic import BaseModel, ConfigDict, Field


class ItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    price: float = Field(ge=0, allow_inf_nan=False)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

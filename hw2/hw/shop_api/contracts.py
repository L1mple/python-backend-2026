from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    name: str
    price: float = Field(ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class ItemReplace(ItemCreate):
    deleted: bool = False


class ItemPatch(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")
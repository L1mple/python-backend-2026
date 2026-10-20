from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ItemInfo(BaseModel):
    name: str
    price: Decimal = Field(ge=0)
    deleted: bool = False

    model_config = ConfigDict(extra="forbid")

class ItemEntity(ItemInfo):
    id: int

class PatchItemInfo(BaseModel):
    name: str | None = None
    price: Decimal | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "PatchItemInfo":
        if not self.model_fields_set:
            raise ValueError("Error: At least one field must be set")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"Error: Field '{field}' mustn't be null")
        return self
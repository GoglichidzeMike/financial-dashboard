from pydantic import BaseModel


class CategoryListResponse(BaseModel):
    items: list[str]

from typing import List
from pydantic import BaseModel


class BulkInviteRequest(BaseModel):
    user_ids: List[str]

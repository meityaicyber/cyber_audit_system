from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ChunkBase(BaseModel):
    section_id: Optional[str] = Field(None, description="Section heading or identifier from report")
    chunk: str = Field(..., description="Text content of the chunk")
    finding_id: Optional[str] = Field(None, description="Associated finding ID if chunk belongs to a finding")
    context_prefix: Optional[str] = Field(None, description="Hierarchical context prefix")
    chunk_index: Optional[int] = Field(None, description="Position within section/report")
    token_count: Optional[int] = Field(None, description="Number of tokens in chunk")
    meta_data: Optional[Dict[str, Any]] = Field(None, description="Arbitrary metadata dictionary")


class ChunkCreate(ChunkBase):
    embedding: Optional[List[float]] = Field(None, description="1024-dimensional dense vector embedding")


class ChunkBatchCreate(BaseModel):
    chunks: List[ChunkCreate]


class ChunkOut(ChunkBase):
    chunk_id: UUID
    report_id: UUID
    created_at: datetime
    updated_at: datetime
    has_embedding: bool = False

    model_config = {"from_attributes": True}


class ChunkSearchRequest(BaseModel):
    query_text: Optional[str] = Field(None, description="Natural language query string")
    query_vector: Optional[List[float]] = Field(None, description="Dense vector embedding of query (1024-dim)")
    report_id: Optional[UUID] = Field(None, description="Restrict search to a specific report")
    section_id: Optional[str] = Field(None, description="Restrict search to a specific section")
    top_k: int = Field(5, ge=1, le=50, description="Number of nearest chunks to return")


class ChunkSearchResult(BaseModel):
    chunk_id: UUID
    report_id: UUID
    section_id: Optional[str] = None
    chunk: str
    finding_id: Optional[str] = None
    distance: float
    score: float
    context_prefix: Optional[str] = None


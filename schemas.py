from typing import List

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    task: str
    owner: str = ""
    deadline: str = ""
    status: str = ""


class OwnerRole(BaseModel):
    name: str
    responsibility: str


class DeadlineItem(BaseModel):
    item: str
    due: str


class OutlineSlide(BaseModel):
    title: str
    bullets: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    topic: str
    summary: List[str] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    owners: List[OwnerRole] = Field(default_factory=list)
    deadlines: List[DeadlineItem] = Field(default_factory=list)
    ppt_outline: List[OutlineSlide] = Field(default_factory=list)


class ChatRequest(BaseModel):
    chat_text: str


class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    ppt_file: str
    ppt_download_url: str
    slides_preview_url: str
    generated_at: str

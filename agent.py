from pilot_app.content import build_content_brief
from pilot_app.llm import LLMJsonClient
from pilot_app.models import ContentBrief, JobCreateRequest
from pilot_app.planner import AgentPlanner


def analyze_im_chat(chat_text: str) -> ContentBrief:
    llm_client = LLMJsonClient()
    request = JobCreateRequest(
        instruction="请从 IM 对话中提炼可交付的汇报内容。",
        chat_text=chat_text,
    )
    plan = AgentPlanner(llm_client).plan(request)
    return build_content_brief(request, plan, llm_client)

from fastapi import APIRouter
from pydantic import BaseModel, Field

from greeting_settings import (
    apply_birthday_templates,
    apply_templates,
    apply_vip_greeting,
    get_greeting_settings,
    save_greeting_settings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class GreetingSettingsBody(BaseModel):
    title_template: str = Field(..., min_length=1, max_length=500)
    subtitle_template: str = Field(..., min_length=1, max_length=500)
    use_smart_rules: bool = False
    birthday_title_template: str = Field(..., min_length=1, max_length=500)
    birthday_subtitle_template: str = Field(..., min_length=1, max_length=500)
    vip_title_template: str = Field(..., min_length=1, max_length=500)
    vip_subtitle_template: str = Field(..., min_length=1, max_length=500)
    vip_title_repeat_template: str = Field(default="", max_length=500)
    vip_subtitle_repeat_template: str = Field(default="", max_length=500)


class GreetingSettingsResponse(BaseModel):
    title_template: str
    subtitle_template: str
    use_smart_rules: bool
    birthday_title_template: str
    birthday_subtitle_template: str
    vip_title_template: str
    vip_subtitle_template: str
    vip_title_repeat_template: str
    vip_subtitle_repeat_template: str


class GreetingPreviewResponse(BaseModel):
    title: str
    subtitle: str


@router.get("/greeting", response_model=GreetingSettingsResponse)
def get_settings():
    return GreetingSettingsResponse(**get_greeting_settings())


@router.put("/greeting", response_model=GreetingSettingsResponse)
def update_settings(body: GreetingSettingsBody):
    s = save_greeting_settings(
        body.title_template,
        body.subtitle_template,
        body.use_smart_rules,
        body.birthday_title_template,
        body.birthday_subtitle_template,
        body.vip_title_template,
        body.vip_subtitle_template,
        body.vip_title_repeat_template,
        body.vip_subtitle_repeat_template,
    )
    return GreetingSettingsResponse(**s)


@router.get("/greeting/preview", response_model=GreetingPreviewResponse)
def preview_greeting(sample_name: str = "Alisher Karimov"):
    return GreetingPreviewResponse(**apply_templates(sample_name))


@router.get("/greeting/preview-birthday", response_model=GreetingPreviewResponse)
def preview_birthday(sample_name: str = "Alisher Karimov"):
    return GreetingPreviewResponse(**apply_birthday_templates(sample_name))


@router.get("/greeting/preview-vip", response_model=GreetingPreviewResponse)
def preview_vip(
    sample_name: str = "Alisher Karimov",
    repeat: bool = False,
):
    vtd = 2 if repeat else 1
    return GreetingPreviewResponse(**apply_vip_greeting(sample_name, vtd))

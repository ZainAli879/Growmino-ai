from __future__ import annotations

import json
import os
from typing import Any

import requests
import streamlit as st


API_DEFAULT = "http://127.0.0.1:8000/generate"
UI_API_TIMEOUT_SECONDS = int(os.getenv("UI_API_TIMEOUT_SECONDS", "300"))

DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

CONTENT_TYPES = [
    "Educational",
    "Educational Carousel Post",
    "Educational Post + Infographic",
    "Pain-point",
    "Case Study",
    "Case Study Post",
    "Industry Insight",
    "Founder Authority",
    "Authority Post (Tips Post)",
    "Automation Tip",
    "Client Testimonial",
    "Testimonial Post",
]

PLATFORMS = ["linkedin", "instagram", "facebook"]
PRESET_LABELS = [
    "None",
    "LinkedIn B2B",
    "Instagram D2C",
    "Facebook Local Service",
    "Food Restaurant",
    "Construction Materials",
    "Car Dealership",
    "Healthcare Clinic",
    "Real Estate Agency",
    "Beauty Salon",
    "Fitness Gym",
    "Online Education",
    "Logistics Company",
    "Electronics E-commerce",
]

PRESETS: dict[str, dict[str, str]] = {
    "LinkedIn B2B": {
        "business_name": "FlowOps Studio",
        "industry": "B2B Automation",
        "offer": "Workflow automation sprints",
        "target_audience": "Operations managers at SMBs",
        "audience_pain_points": "Manual follow-ups and inconsistent handoffs",
        "weekly_focus_topic": "Reducing lead handoff bottlenecks",
        "day": "Monday",
        "content_type": "Educational",
        "tone": "Practical and confident",
        "brand_personality": "Direct, modern, helpful",
        "proof_assets": "",
        "platform": "linkedin",
    },
    "Instagram D2C": {
        "business_name": "UrbanWear Boutique",
        "industry": "Fashion Retail",
        "offer": "Trend-led streetwear with same-day dispatch",
        "target_audience": "Gen Z and young millennials",
        "audience_pain_points": "Late deliveries and wrong sizes",
        "weekly_focus_topic": "How to speed up order fulfillment",
        "day": "Saturday",
        "content_type": "Automation Tip",
        "tone": "Energetic and relatable",
        "brand_personality": "Playful, fast, customer-first",
        "proof_assets": "",
        "platform": "instagram",
    },
    "Facebook Local Service": {
        "business_name": "BrightHome Repairs",
        "industry": "Home Services",
        "offer": "Same-week maintenance visits",
        "target_audience": "Homeowners in the city",
        "audience_pain_points": "No-shows and unclear service timelines",
        "weekly_focus_topic": "Reliable booking and service updates",
        "day": "Thursday",
        "content_type": "Industry Insight",
        "tone": "Friendly and reassuring",
        "brand_personality": "Helpful, honest, reliable",
        "proof_assets": "",
        "platform": "facebook",
    },
    "Food Restaurant": {
        "business_name": "SpiceRoute Kitchen",
        "industry": "Food & Beverage",
        "offer": "Fresh family meal combos with 30-minute delivery",
        "target_audience": "Busy families and working professionals",
        "audience_pain_points": "Long wait times and inconsistent food quality",
        "weekly_focus_topic": "Faster order prep without compromising taste",
        "day": "Tuesday",
        "content_type": "Pain-point",
        "tone": "Friendly and appetizing",
        "brand_personality": "Warm, quick, quality-focused",
        "proof_assets": "",
        "platform": "instagram",
    },
    "Construction Materials": {
        "business_name": "BuildCore Materials",
        "industry": "Construction Supply",
        "offer": "Bulk cement, steel, and aggregates with scheduled delivery",
        "target_audience": "Contractors and project procurement teams",
        "audience_pain_points": "Stock delays and variable material quality",
        "weekly_focus_topic": "Reducing project delays through supply planning",
        "day": "Thursday",
        "content_type": "Industry Insight",
        "tone": "Professional and practical",
        "brand_personality": "Dependable, direct, technical",
        "proof_assets": "",
        "platform": "linkedin",
    },
    "Car Dealership": {
        "business_name": "CityDrive Motors",
        "industry": "Automotive Retail",
        "offer": "Certified pre-owned cars with financing support",
        "target_audience": "First-time buyers and growing families",
        "audience_pain_points": "Trust issues, hidden costs, complex paperwork",
        "weekly_focus_topic": "How to buy a used car without surprises",
        "day": "Monday",
        "content_type": "Educational",
        "tone": "Helpful and transparent",
        "brand_personality": "Honest, modern, customer-first",
        "proof_assets": "",
        "platform": "facebook",
    },
    "Healthcare Clinic": {
        "business_name": "WellSpring Family Clinic",
        "industry": "Primary Healthcare",
        "offer": "Same-day appointments and preventive care plans",
        "target_audience": "Families and working adults",
        "audience_pain_points": "Long appointment wait times and unclear follow-ups",
        "weekly_focus_topic": "Improving patient communication and appointment flow",
        "day": "Saturday",
        "content_type": "Automation Tip",
        "tone": "Calm and reassuring",
        "brand_personality": "Trustworthy, caring, clear",
        "proof_assets": "",
        "platform": "facebook",
    },
    "Real Estate Agency": {
        "business_name": "NorthPoint Realty",
        "industry": "Real Estate",
        "offer": "Buyer and seller representation for urban homes",
        "target_audience": "First-time home buyers and move-up families",
        "audience_pain_points": "Decision fatigue and unclear next steps",
        "weekly_focus_topic": "What buyers should check before making an offer",
        "day": "Friday",
        "content_type": "Founder Authority",
        "tone": "Confident and advisory",
        "brand_personality": "Local expert, straightforward, responsive",
        "proof_assets": "",
        "platform": "linkedin",
    },
    "Beauty Salon": {
        "business_name": "LuxeGlow Studio",
        "industry": "Beauty & Personal Care",
        "offer": "Hair, skin, and bridal makeover packages",
        "target_audience": "Women aged 20-40 planning events or regular upkeep",
        "audience_pain_points": "Last-minute slot issues and uneven service quality",
        "weekly_focus_topic": "How to secure prime appointment slots stress-free",
        "day": "Tuesday",
        "content_type": "Pain-point",
        "tone": "Stylish and relatable",
        "brand_personality": "Trendy, attentive, premium",
        "proof_assets": "",
        "platform": "instagram",
    },
    "Fitness Gym": {
        "business_name": "IronPulse Fitness",
        "industry": "Health & Fitness",
        "offer": "Coach-led transformation programs with habit tracking",
        "target_audience": "Working adults trying to stay consistent",
        "audience_pain_points": "Losing motivation and inconsistent routines",
        "weekly_focus_topic": "3-step system to stay consistent with workouts",
        "day": "Monday",
        "content_type": "Educational",
        "tone": "Motivating and practical",
        "brand_personality": "Disciplined, supportive, energetic",
        "proof_assets": "",
        "platform": "instagram",
    },
    "Online Education": {
        "business_name": "SkillBridge Academy",
        "industry": "EdTech",
        "offer": "Job-ready digital skills bootcamps",
        "target_audience": "Students and early-career professionals",
        "audience_pain_points": "Course overload and lack of clear learning paths",
        "weekly_focus_topic": "Choosing the right skills roadmap for career growth",
        "day": "Thursday",
        "content_type": "Industry Insight",
        "tone": "Encouraging and clear",
        "brand_personality": "Practical mentor, modern, accessible",
        "proof_assets": "",
        "platform": "linkedin",
    },
    "Logistics Company": {
        "business_name": "SwiftLane Logistics",
        "industry": "Logistics & Supply Chain",
        "offer": "Last-mile and regional freight delivery services",
        "target_audience": "E-commerce brands and wholesalers",
        "audience_pain_points": "Late deliveries and low shipment visibility",
        "weekly_focus_topic": "Reducing delivery exceptions with process automation",
        "day": "Saturday",
        "content_type": "Automation Tip",
        "tone": "Operational and confident",
        "brand_personality": "Reliable, fast, data-driven",
        "proof_assets": "",
        "platform": "linkedin",
    },
    "Electronics E-commerce": {
        "business_name": "VoltCart Store",
        "industry": "Consumer Electronics",
        "offer": "Curated gadgets with warranty and fast shipping",
        "target_audience": "Tech-savvy shoppers and gift buyers",
        "audience_pain_points": "Confusing product choices and return concerns",
        "weekly_focus_topic": "How to pick the right gadget without overspending",
        "day": "Wednesday",
        "content_type": "Case Study",
        "tone": "Smart and concise",
        "brand_personality": "Helpful, credible, up-to-date",
        "proof_assets": "",
        "platform": "facebook",
    },
}


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background: linear-gradient(145deg, #0f172a 0%, #1e293b 45%, #334155 100%);
                color: #e2e8f0;
            }
            .block-container {
                max-width: 920px;
                padding-top: 2rem;
                padding-bottom: 2rem;
            }
            h1, h2, h3, p, label, .stMarkdown, .stCaption {
                color: #e2e8f0 !important;
            }
            [data-testid="stExpander"] {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid #475569;
                border-radius: 14px;
            }
            .card {
                background: rgba(15, 23, 42, 0.78);
                border: 1px solid #64748b;
                border-radius: 16px;
                padding: 14px 16px;
                margin-bottom: 12px;
                color: #e2e8f0;
            }
            [data-testid="stTextInput"] input,
            [data-testid="stTextArea"] textarea,
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
                background: #0b1220 !important;
                color: #f8fafc !important;
                border: 1px solid #64748b !important;
            }
            [data-testid="stTextInput"] input::placeholder,
            [data-testid="stTextArea"] textarea::placeholder {
                color: #94a3b8 !important;
            }
            .stButton > button,
            [data-testid="stFormSubmitButton"] button {
                background: #22d3ee !important;
                color: #0b1120 !important;
                border: none !important;
                font-weight: 600 !important;
            }
            [data-testid="stCodeBlock"] {
                background: #0b1220 !important;
                border: 1px solid #64748b !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _default_payload() -> dict[str, Any]:
    return {
        "business_name": "",
        "industry": "",
        "offer": "",
        "target_audience": "",
        "audience_pain_points": "",
        "weekly_focus_topic": "",
        "day": "Monday",
        "content_type": "Educational",
        "tone": "",
        "brand_personality": "",
        "proof_assets": "",
        "company_logo_url": "",
        "platform": "linkedin",
    }


def _render_form() -> dict[str, Any]:
    preset_label = st.selectbox("Quick preset", PRESET_LABELS, index=0)
    defaults = PRESETS.get(preset_label, _default_payload())

    with st.form("generate_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            business_name = st.text_input("Business name", value=defaults["business_name"])
            industry = st.text_input("Industry", value=defaults["industry"])
            offer = st.text_input("Offer", value=defaults["offer"])
            target_audience = st.text_input("Target audience", value=defaults["target_audience"])
            audience_pain_points = st.text_area("Audience pain points", value=defaults["audience_pain_points"], height=90)
            weekly_focus_topic = st.text_input("Weekly focus topic", value=defaults["weekly_focus_topic"])
        with col2:
            day = st.selectbox("Day", DAYS, index=DAYS.index(defaults["day"]))
            content_type = st.selectbox("Content type", CONTENT_TYPES, index=CONTENT_TYPES.index(defaults["content_type"]))
            platform = st.selectbox("Platform", PLATFORMS, index=PLATFORMS.index(defaults["platform"]))
            tone = st.text_input("Tone", value=defaults["tone"])
            brand_personality = st.text_input("Brand personality", value=defaults["brand_personality"])
            proof_assets = st.text_area("Proof assets (optional)", value=defaults["proof_assets"], height=90)
            company_logo_url = st.text_input(
                "Company logo URL/path (optional)",
                value=defaults.get("company_logo_url", ""),
            )

        submit = st.form_submit_button("Generate Caption + Image", use_container_width=True)
        if not submit:
            return {}

        return {
            "business_name": business_name,
            "industry": industry,
            "offer": offer,
            "target_audience": target_audience,
            "audience_pain_points": audience_pain_points,
            "weekly_focus_topic": weekly_focus_topic,
            "day": day,
            "content_type": content_type,
            "tone": tone,
            "brand_personality": brand_personality,
            "proof_assets": proof_assets,
            "company_logo_url": company_logo_url,
            "platform": platform,
        }


def _call_api(api_url: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | str]:
    response = requests.post(api_url, json=payload, timeout=UI_API_TIMEOUT_SECONDS)
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return response.status_code, body


def main() -> None:
    st.set_page_config(page_title="AI Post Generator", page_icon=":brain:", layout="centered")
    _inject_styles()

    st.title("AI Post Generator")
    st.caption("Generate one platform-ready caption and one aligned image.")

    with st.expander("API Settings", expanded=True):
        api_url = st.text_input("Backend endpoint", value=API_DEFAULT)
        st.code("Run backend: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")

    st.markdown('<div class="card">Fill details and submit.</div>', unsafe_allow_html=True)

    payload = _render_form()
    if not payload:
        return

    with st.spinner("Generating..."):
        try:
            status, body = _call_api(api_url=api_url, payload=payload)
        except requests.RequestException as exc:
            st.error(f"Could not reach backend API: {exc}")
            return

    if status != 200:
        st.error(f"API error ({status})")
        st.code(json.dumps(body, indent=2) if isinstance(body, dict) else str(body))
        return

    if not isinstance(body, dict):
        st.error("Unexpected API response format.")
        st.code(str(body))
        return

    st.success("Generated successfully.")
    st.subheader("Headline")
    st.text_input("Final headline", value=body.get("headline", ""), disabled=True)

    st.subheader("Caption")
    st.text_area("Final caption", value=body.get("caption", ""), height=260)

    image_info = body.get("openai_image", {})
    image_path = image_info.get("file_path", "")
    if image_path:
        st.subheader("Image")
        st.image(image_path, caption=image_info.get("alt_text", "Generated image"), use_container_width=True)
        st.code(f"Saved at: {image_path}")

    st.subheader("QA")
    qa = body.get("qa", {}) or {}
    warnings = qa.get("warnings", []) if isinstance(qa, dict) else []
    if warnings:
        st.warning("QA warnings: " + " | ".join(warnings))
    st.json(qa)

    st.subheader("Trace")
    st.json(body.get("trace", {}))


if __name__ == "__main__":
    main()

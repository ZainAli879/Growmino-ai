from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chains import generate_image_prompt_from_caption  # noqa: E402
from app.schemas import GenerateRequest  # noqa: E402


class FakeImagePromptChain:
    def __init__(self) -> None:
        self.inputs = None

    def invoke(self, inputs):
        self.inputs = inputs
        return "Premium editorial fashion campaign showing garment details and confident everyday styling."


class ImagePromptStrategyTests(unittest.TestCase):
    def test_image_prompt_uses_business_context_and_quality_contract(self) -> None:
        fake_chain = FakeImagePromptChain()
        payload = GenerateRequest(
            business_name="Velmora",
            industry="Clothes & Accessories - Men's Fashion",
            offer="Affordable premium everyday shirts and trousers",
            target_audience="Style-conscious young professionals",
            audience_pain_points="They want polished outfits without premium prices.",
            weekly_focus_topic="Affordable style for weekday outfits",
            day="Monday",
            content_type="Educational",
            tone="Confident and aspirational",
            brand_personality="Modern, clean, stylish",
            cta_preference="Shop the new collection",
            proof_assets="Known for breathable fabrics and versatile fits",
            company_logo_url="",
            platform="instagram",
        )

        with patch("app.chains._build_image_prompt_chain", return_value=fake_chain):
            prompt = generate_image_prompt_from_caption(
                payload=payload,
                caption="Build a weekday wardrobe that looks sharp without overspending.",
                headline="Weekday Style Made Simple",
                logo_instruction="Do not generate logos.",
                api_key="test-key",
                model_name="test-model",
            )

        self.assertEqual(fake_chain.inputs["cta_preference"], "Shop the new collection")
        self.assertEqual(fake_chain.inputs["proof_assets"], "Known for breathable fabrics and versatile fits")
        self.assertIn("Final creative quality contract", prompt)
        self.assertIn("Clothes & Accessories - Men's Fashion", prompt)
        self.assertIn("Affordable premium everyday shirts and trousers", prompt)
        self.assertIn("Avoid generic stock-photo scenes", prompt)


if __name__ == "__main__":
    unittest.main()

"""The schema we ask the LLM to fill must exclude fields we already know locally.

Regression cover for the truncation bug found by evals 2026-08-27: `raw_text`
asked the model to retype the entire resume, which roughly doubled output tokens
and made qwen3:8b fall into a repeated-"\\n" loop that cut the response off
mid-string. An unterminated string makes the WHOLE document unparseable, so
fixtures whose name/email/phone were extracted perfectly still scored 0%.
"""
import json

from backend.utils.resume_parsing.contracts.resume_contract import ResumeV2
from backend.utils.resume_parsing.extractors.structured_extractor import (
    MODEL_EXCLUDED_FIELDS,
    ExtractionContract,
    create_extraction_prompt,
    extraction_schema,
)


def test_raw_text_excluded_from_extraction_schema():
    assert "raw_text" in ResumeV2.model_fields, "precondition: contract still has raw_text"
    assert "raw_text" not in extraction_schema()["properties"]


def test_every_other_contract_field_survives():
    """Exclusion must be surgical — dropping a real extraction target would
    silently lower recall instead of raising it."""
    expected = set(ResumeV2.model_fields) - set(MODEL_EXCLUDED_FIELDS)
    assert set(extraction_schema()["properties"]) == expected


def test_excluded_fields_are_not_required():
    assert not set(extraction_schema().get("required", [])) & set(MODEL_EXCLUDED_FIELDS)


def test_extraction_contract_is_a_pydantic_model():
    """Providers branch on Pydantic-model-ness to pick their native structured
    path (Anthropic messages.parse, Ollama format). A plain dict would silently
    downgrade those to best-effort JSON."""
    from pydantic import BaseModel

    assert isinstance(ExtractionContract, type) and issubclass(ExtractionContract, BaseModel)
    assert "raw_text" not in ExtractionContract.model_fields


def test_extracted_doc_without_raw_text_still_validates_against_contract():
    """Downstream still stores ResumeV2; raw_text is filled in locally."""
    doc = ExtractionContract(personal_info={"name": "Maya Chen"}).model_dump(mode="json")
    resume = ResumeV2(**doc, raw_text="original text")
    assert resume.raw_text == "original text"


def test_prompt_does_not_instruct_the_model_to_emit_raw_text():
    prompt = create_extraction_prompt("Maya Chen\nEngineer", extraction_schema())
    schema_block = prompt[prompt.index("{") :] if "{" in prompt else ""
    assert '"raw_text"' not in schema_block
    # and the embedded schema is still valid JSON the model can follow
    assert json.dumps(extraction_schema())

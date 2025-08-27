"""
Section Classifier Processor
Uses a trained model to classify blocks of text into resume sections.
"""
import logging
import pickle
import os
from typing import Dict, List, Optional, Any, Tuple

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

# Define the root directory of the project to locate the models
# This assumes the script is run from the project root (e.g., RecruitIQ/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
DEFAULT_MODELS_DIR = os.path.join(PROJECT_ROOT, 'training_data', 'parsing', 'models')


class SectionClassifierProcessor(BaseProcessor):
    """
    A processor that uses a machine learning model to classify text blocks into predefined sections.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the SectionClassifierProcessor.

        Args:
            config (Optional[Dict[str, Any]]): Configuration dictionary.
                                                 Can contain 'models_dir' to specify model location.
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        models_dir = self.config.get('models_dir', DEFAULT_MODELS_DIR)
        
        try:
            self.model, self.vectorizer = self._load_artifacts(models_dir)
            self.logger.info("SectionClassifierProcessor initialized with trained model.")
        except FileNotFoundError:
            self.model, self.vectorizer = None, None
            self.logger.error(f"Model artifacts not found in {models_dir}. "
                              "The processor will not be able to classify sections. "
                              "Please run the training script first.")

    def _load_artifacts(self, models_dir: str) -> Tuple[Any, Any]:
        """
        Loads the classification model and vectorizer from the specified directory.
        """
        model_path = os.path.join(models_dir, 'section_classifier_model.pkl')
        vectorizer_path = os.path.join(models_dir, 'section_classifier_vectorizer.pkl')

        if not os.path.exists(model_path) or not os.path.exists(vectorizer_path):
            raise FileNotFoundError(f"Model or vectorizer not found in {models_dir}")

        self.logger.info(f"Loading model from {model_path}")
        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        self.logger.info(f"Loading vectorizer from {vectorizer_path}")
        with open(vectorizer_path, 'rb') as f:
            vectorizer = pickle.load(f)
            
        return model, vectorizer

    def _classify_blocks(self, blocks: List[str]) -> List[str]:
        """
        Classifies a list of text blocks into sections using the loaded model.
        """
        if not self.model or not self.vectorizer:
            self.logger.warning("Model/vectorizer not loaded. Returning 'general' for all blocks.")
            return ['general'] * len(blocks)
            
        # Transform the text blocks using the TF-IDF vectorizer
        X_vec = self.vectorizer.transform(blocks)
        
        # Predict the section for each block
        predictions = self.model.predict(X_vec)
        
        return predictions

    async def process(self, markdown: str) -> Dict[str, str]:
        """
        Processes the markdown text, classifying each block into a section.

        Args:
            markdown (str): The markdown-formatted resume text.

        Returns:
            Dict[str, str]: A dictionary mapping section names to their content.
        """
        if not markdown:
            return {"general": ""}

        # Split the markdown into blocks (e.g., by paragraphs or logical units)
        blocks = [block.strip() for block in markdown.split('\n\n') if block.strip()]
        self.logger.info(f"SEC_CLASS: Blocks before classification (first 5): {blocks[:5]}") # TEMP INFO LINE
        self.logger.info(f"SEC_CLASS: Total blocks: {len(blocks)}") # TEMP INFO LINE
        
        if not blocks:
            return {"general": markdown}

        # Define canonical headers (ensure keys are uppercase as produced by MarkdownProcessor)
        CANONICAL_HEADERS = {
            "## WORK EXPERIENCE": "experience",
            "## PROFESSIONAL EXPERIENCE": "experience",
            "## EMPLOYMENT": "experience",
            "## CAREER HISTORY": "experience",
            "## EXPERIENCE": "experience",
            "## WORK HISTORY": "experience",
            "## EMPLOYMENT HISTORY": "experience",
            "## PROFESSIONAL BACKGROUND": "experience",
            "## EDUCATION": "education",
            "## ACADEMIC BACKGROUND": "education",
            "## SKILLS": "skills",
            "## TECHNICAL SKILLS": "skills",
            "## CORE COMPETENCIES": "skills",
            "## EXPERTISE": "skills",
            "## QUALIFICATIONS": "skills",
            "## PROFILE": "summary",
            "## SUMMARY": "summary",
            "## OBJECTIVE": "summary",
            "## ABOUT": "summary",
            "## OVERVIEW": "summary",
            "## PROJECTS": "projects",
            "## PROJECT EXPERIENCE": "projects",
            "## PERSONAL PROJECTS": "projects",
            # Add more common variations as needed
        }

        # Classify all blocks at once
        predicted_labels = self._classify_blocks(blocks)
        section_labels = []
        for i, block in enumerate(blocks):
            # Check for canonical header override
            # Strip any potential leading/trailing whitespace from block just in case, though split().strip() should handle it.
            normalized_block = block.strip()
            if normalized_block in CANONICAL_HEADERS:
                section_labels.append(CANONICAL_HEADERS[normalized_block])
                self.logger.info(f"SEC_CLASS: Overriding classification for block '{normalized_block}' to '{CANONICAL_HEADERS[normalized_block]}'")
            else:
                section_labels.append(predicted_labels[i])

        # Group blocks by their predicted section
        sections: Dict[str, List[str]] = {}
        for block, label in zip(blocks, section_labels):
            sections.setdefault(label, []).append(block)

        # Join the blocks for each section back into a single string
        processed_sections = {k: "\n\n".join(v) for k, v in sections.items() if v}

        self.logger.info(f"SEC_CLASS: Section keys after classification: {list(processed_sections.keys())}")
        return processed_sections

#!/usr/bin/env python
"""
Script to evaluate resume parsing models by comparing their performance on a test dataset.
This compares the local Ollama model against LLM-based solutions like Cohere and Meta Llama.
"""
import json
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import services
from backend.services.local_model_service import get_local_model_service
from backend.services.llm_service import get_llm_service
from backend.utils.config import get_settings

class ParsingEvaluator:
    """Evaluator for resume parsing models."""
    
    def __init__(self, test_data_path: str):
        """
        Initialize the evaluator with test data.
        
        Args:
            test_data_path: Path to the test data JSON file
        """
        self.test_data_path = test_data_path
        self.test_data = []
        self.load_test_data()
        
        # Initialize services
        self.settings = get_settings()
        self.llm_service = get_llm_service(self.settings)
        self.local_model_service = get_local_model_service()
        
        # Fields to evaluate
        self.fields = {
            "personal_info": ["name", "email", "phone", "location"],
            "education": ["degree", "institution"],
            "experience": ["title", "company"],
            "skills": []  # Skills are evaluated differently (set overlap)
        }
        
    def load_test_data(self):
        """Load test data from JSON file."""
        try:
            with open(self.test_data_path, 'r') as f:
                self.test_data = json.load(f)
            logger.info(f"Loaded {len(self.test_data)} test examples from {self.test_data_path}")
        except Exception as e:
            logger.error(f"Error loading test data: {str(e)}")
            self.test_data = []
    
    async def evaluate_all_models(self, max_examples: int = 10):
        """
        Evaluate all models on the test dataset.
        
        Args:
            max_examples: Maximum number of examples to evaluate (for faster testing)
        
        Returns:
            Dict containing evaluation metrics for each model
        """
        # Limit the number of examples for evaluation
        examples = self.test_data[:max_examples]
        if not examples:
            logger.error("No test examples available")
            return {}
        
        logger.info(f"Evaluating models on {len(examples)} examples")
        
        # Create metrics structure
        metrics = {
            "local_model": {"correct": 0, "total": 0, "fields": {}},
            "cohere": {"correct": 0, "total": 0, "fields": {}},
            "meta_llama": {"correct": 0, "total": 0, "fields": {}}
        }
        
        # Initialize field metrics
        for model in metrics:
            for field_group in self.fields:
                metrics[model]["fields"][field_group] = {"correct": 0, "total": 0}
        
        # Process each example
        for i, example in enumerate(examples):
            logger.info(f"Evaluating example {i+1}/{len(examples)}")
            resume_text = example["input"]
            expected = example["output"]
            
            # Get results from each model
            results = {
                "local_model": await self.local_model_service.parse_resume(resume_text),
                "cohere": await self.llm_service.extract_structured_resume_with_cohere(resume_text),
                "meta_llama": await self.get_meta_llama_parsing(resume_text)
            }
            
            # Calculate accuracy metrics
            await self.calculate_metrics(results, expected, metrics)
        
        # Calculate final scores
        self.calculate_final_scores(metrics)
        
        return metrics
    
    async def get_meta_llama_parsing(self, resume_text: str) -> Dict:
        """Get parsing result from Meta Llama."""
        try:
            # Format prompt for structured parsing
            prompt = (
                "Extract structured information from this resume as a JSON object with "
                "personal_info, education, experience, and skills fields:\n\n" + resume_text
            )
            
            # Use the Meta Llama model through the LLM service
            llm = self.llm_service.get_llm("meta_llama")
            response = await llm.ainvoke(prompt)
            
            # Try to extract JSON from the response
            import re
            import json
            
            # Find JSON pattern in response
            json_match = re.search(r'(\{.*\})', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    logger.warning("Failed to parse JSON from Meta Llama response")
            
            return {}
        except Exception as e:
            logger.error(f"Error getting Meta Llama parsing: {str(e)}")
            return {}
    
    async def calculate_metrics(self, results: Dict, expected: Dict, metrics: Dict):
        """
        Calculate accuracy metrics for each model's results.
        
        Args:
            results: Dict of results from each model
            expected: Expected output (ground truth)
            metrics: Metrics dictionary to update
        """
        # Process each model's results
        for model, result in results.items():
            # Skip if result is empty
            if not result:
                logger.warning(f"{model} returned empty result")
                continue
            
            # Evaluate each field group
            for field_group in self.fields:
                # Skip if field group doesn't exist in expected or result
                if field_group not in expected or field_group not in result:
                    continue
                
                expected_group = expected[field_group]
                result_group = result[field_group]
                
                # Handle different field groups differently
                if field_group == "skills":
                    # Skills are evaluated as set overlap
                    expected_skills = set([s.lower() for s in expected_group])
                    result_skills = set([s.lower() for s in result_group])
                    
                    # Calculate overlap
                    if expected_skills:
                        overlap = len(expected_skills.intersection(result_skills))
                        metrics[model]["fields"][field_group]["total"] += len(expected_skills)
                        metrics[model]["fields"][field_group]["correct"] += overlap
                        
                        # Update overall counts
                        metrics[model]["total"] += len(expected_skills)
                        metrics[model]["correct"] += overlap
                
                elif field_group in ["personal_info"]:
                    # For personal_info, check each field individually
                    for field in self.fields[field_group]:
                        if field in expected_group and expected_group[field]:
                            metrics[model]["fields"][field_group]["total"] += 1
                            metrics[model]["total"] += 1
                            
                            # Check if field exists and is similar
                            if field in result_group and self.is_similar(result_group[field], expected_group[field]):
                                metrics[model]["fields"][field_group]["correct"] += 1
                                metrics[model]["correct"] += 1
                
                else:
                    # For education and experience, check each entry's fields
                    expected_entries = expected_group if isinstance(expected_group, list) else []
                    result_entries = result_group if isinstance(result_group, list) else []
                    
                    # For each expected entry, find best matching result entry
                    for exp_entry in expected_entries:
                        best_match_score = 0
                        best_match = None
                        
                        for res_entry in result_entries:
                            match_score = self.calculate_entry_match(exp_entry, res_entry, self.fields[field_group])
                            if match_score > best_match_score:
                                best_match_score = match_score
                                best_match = res_entry
                        
                        # Count fields in this entry
                        for field in self.fields[field_group]:
                            if field in exp_entry and exp_entry[field]:
                                metrics[model]["fields"][field_group]["total"] += 1
                                metrics[model]["total"] += 1
                                
                                # Check if match found and field is similar
                                if best_match and field in best_match and self.is_similar(best_match[field], exp_entry[field]):
                                    metrics[model]["fields"][field_group]["correct"] += 1
                                    metrics[model]["correct"] += 1
    
    def calculate_entry_match(self, expected: Dict, result: Dict, fields: List[str]) -> float:
        """
        Calculate how well an entry matches the expected entry.
        
        Args:
            expected: Expected entry
            result: Result entry
            fields: Fields to compare
            
        Returns:
            Float score between 0 and 1
        """
        if not expected or not result:
            return 0
        
        score = 0
        total = 0
        
        for field in fields:
            if field in expected and expected[field] and field in result and result[field]:
                total += 1
                if self.is_similar(result[field], expected[field]):
                    score += 1
        
        return score / total if total > 0 else 0
    
    def is_similar(self, str1: str, str2: str) -> bool:
        """
        Check if two strings are similar (case-insensitive, partial match).
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Boolean indicating similarity
        """
        if not str1 or not str2:
            return False
            
        str1 = str(str1).lower().strip()
        str2 = str(str2).lower().strip()
        
        # Exact match
        if str1 == str2:
            return True
            
        # Substring match (either way)
        if str1 in str2 or str2 in str1:
            return True
            
        # Simple word overlap (at least 50% of words match)
        words1 = set(str1.split())
        words2 = set(str2.split())
        if len(words1) > 0 and len(words2) > 0:
            overlap = len(words1.intersection(words2))
            return overlap >= min(len(words1), len(words2)) / 2
            
        return False
    
    def calculate_final_scores(self, metrics: Dict):
        """
        Calculate final accuracy scores for each model.
        
        Args:
            metrics: Metrics dictionary to update
        """
        for model in metrics:
            # Calculate overall accuracy
            if metrics[model]["total"] > 0:
                metrics[model]["accuracy"] = metrics[model]["correct"] / metrics[model]["total"]
            else:
                metrics[model]["accuracy"] = 0
                
            # Calculate field group accuracies
            for field_group in self.fields:
                if field_group in metrics[model]["fields"]:
                    if metrics[model]["fields"][field_group]["total"] > 0:
                        metrics[model]["fields"][field_group]["accuracy"] = (
                            metrics[model]["fields"][field_group]["correct"] / 
                            metrics[model]["fields"][field_group]["total"]
                        )
                    else:
                        metrics[model]["fields"][field_group]["accuracy"] = 0

async def main():
    """Run the evaluation script."""
    parser_dir = Path("./training_data/parsing")
    test_data_path = parser_dir / "resume_parsing_test.json"
    
    if not test_data_path.exists():
        logger.error(f"Test data not found at {test_data_path}")
        logger.info("Run create_parsing_dataset.py first to generate test data")
        return
    
    # Create evaluator
    evaluator = ParsingEvaluator(str(test_data_path))
    
    # Run evaluation
    logger.info("Starting model evaluation...")
    start_time = time.time()
    metrics = await evaluator.evaluate_all_models(max_examples=5)  # Start with a small number for testing
    end_time = time.time()
    
    # Print results
    print("\n===== PARSING MODEL EVALUATION RESULTS =====")
    print(f"Evaluation completed in {end_time - start_time:.2f} seconds\n")
    
    for model, metric in metrics.items():
        print(f"MODEL: {model.upper()}")
        print(f"Overall Accuracy: {metric.get('accuracy', 0):.2%}")
        
        print("Field Accuracies:")
        for field_group, field_metric in metric["fields"].items():
            accuracy = field_metric.get("accuracy", 0)
            print(f"  - {field_group}: {accuracy:.2%}")
        print()
    
    # Save results to file
    results_file = parser_dir / "evaluation_results.json"
    with open(results_file, "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"Evaluation results saved to {results_file}")
    
    # Determine best model
    best_model = max(metrics.items(), key=lambda x: x[1].get("accuracy", 0))[0]
    print(f"\nBest performing model: {best_model.upper()}")
    
    # Recommendation based on results
    if "local_model" in metrics and metrics["local_model"].get("accuracy", 0) >= 0.7:
        print("\nRECOMMENDATION: The local model performs well and can be used for production.")
    elif "local_model" in metrics and metrics["local_model"].get("accuracy", 0) >= 0.5:
        print("\nRECOMMENDATION: The local model performs adequately but could benefit from more training data.")
    else:
        print("\nRECOMMENDATION: The local model needs improvement. Consider continuing with API-based parsing for now.")

if __name__ == "__main__":
    asyncio.run(main())

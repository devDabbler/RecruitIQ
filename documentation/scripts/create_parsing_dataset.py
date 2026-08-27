#!/usr/bin/env python
"""
Script to create a training dataset for resume parsing from existing parsed resumes.
This extracts examples from your database to create training pairs of raw text and structured data.
"""
import json
import os
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directory to store training data
DATA_DIR = Path("./training_data/parsing")

async def create_parsing_dataset(num_samples: int = 5, output_dir: str = None):
    """
    Create a dataset of resume parsing examples.
    Since we can't directly access the database in this environment,
    we'll create synthetic examples for demonstration purposes.
    
    Args:
        num_samples: Number of synthetic examples to generate
        output_dir: Directory to save the dataset (default: ./training_data/parsing)
    """
    # Set up output directory
    if output_dir:
        data_dir = Path(output_dir)
    else:
        data_dir = DATA_DIR
    
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create synthetic examples
    logger.info(f"Creating {num_samples} synthetic resume examples")
    
    examples = []
    
    # Example 1: Software Engineer
    examples.append({
        "input": """John Smith
Senior Software Engineer
john.smith@example.com | (555) 123-4567 | San Francisco, CA
LinkedIn: linkedin.com/in/johnsmith

SUMMARY
Experienced software engineer with 8+ years developing web applications using Python, JavaScript, and cloud technologies. Specialized in backend development and API design.

EXPERIENCE
Senior Software Engineer, Tech Solutions Inc. (Jan 2020 - Present)
- Led development of microservices architecture using FastAPI and Docker
- Implemented CI/CD pipelines reducing deployment time by 40%
- Mentored junior developers and conducted code reviews

Software Developer, Data Innovations Corp (Mar 2018 - Dec 2019)
- Developed data processing pipelines using Python and Apache Spark
- Created RESTful APIs for internal and external consumption
- Improved system performance by 30% through query optimization

Junior Developer, WebStart LLC (Jun 2016 - Feb 2018)
- Built responsive web applications using React and Node.js
- Collaborated with design team to implement UI/UX improvements

EDUCATION
University of California, Berkeley (2012-2016)
B.S. Computer Science, GPA: 3.8/4.0

SKILLS
Languages: Python, JavaScript, SQL, HTML/CSS
Frameworks: FastAPI, Django, React, Express.js
Tools: Docker, Kubernetes, AWS, Git, Jenkins
Databases: PostgreSQL, MongoDB, Redis
""",
        "output": {
            "personal_info": {
                "name": "John Smith",
                "email": "john.smith@example.com",
                "phone": "(555) 123-4567",
                "location": "San Francisco, CA",
                "linkedin": "linkedin.com/in/johnsmith"
            },
            "skills": [
                "Python", "JavaScript", "SQL", "HTML/CSS", "FastAPI", "Django",
                "React", "Express.js", "Docker", "Kubernetes", "AWS", "Git", 
                "Jenkins", "PostgreSQL", "MongoDB", "Redis"
            ],
            "education": [
                {
                    "degree": "B.S. Computer Science",
                    "institution": "University of California, Berkeley",
                    "date_range": "2012-2016",
                    "gpa": "3.8/4.0"
                }
            ],
            "experience": [
                {
                    "title": "Senior Software Engineer",
                    "company": "Tech Solutions Inc.",
                    "date_range": "Jan 2020 - Present",
                    "description": "- Led development of microservices architecture using FastAPI and Docker\n- Implemented CI/CD pipelines reducing deployment time by 40%\n- Mentored junior developers and conducted code reviews"
                },
                {
                    "title": "Software Developer",
                    "company": "Data Innovations Corp",
                    "date_range": "Mar 2018 - Dec 2019",
                    "description": "- Developed data processing pipelines using Python and Apache Spark\n- Created RESTful APIs for internal and external consumption\n- Improved system performance by 30% through query optimization"
                },
                {
                    "title": "Junior Developer",
                    "company": "WebStart LLC",
                    "date_range": "Jun 2016 - Feb 2018",
                    "description": "- Built responsive web applications using React and Node.js\n- Collaborated with design team to implement UI/UX improvements"
                }
            ]
        }
    })
    
    # Example 2: Data Scientist
    examples.append({
        "input": """Sarah Johnson
Data Scientist
sarah.johnson@example.com | (555) 987-6543
Boston, MA | github.com/sarahjohnson

SUMMARY
Data scientist with expertise in machine learning, statistical analysis, and data visualization. 5+ years experience building predictive models and deriving insights from complex datasets.

EXPERIENCE
Senior Data Scientist, Analytics Co. (Aug 2021 - Present)
• Developed machine learning models to predict customer churn with 85% accuracy
• Created interactive dashboards using Tableau for executive decision-making
• Led a team of 3 junior data scientists on various analytics projects

Data Scientist, Research Systems Inc. (May 2018 - July 2021)
• Built NLP algorithms for text classification and sentiment analysis
• Implemented recommendation systems using collaborative filtering
• Optimized data pipelines reducing processing time by 50%

Data Analyst, Financial Services Group (Jan 2016 - Apr 2018)
• Performed statistical analysis on financial datasets
• Generated monthly reports and visualizations for stakeholders

EDUCATION
Massachusetts Institute of Technology (MIT) (2014-2016)
M.S. Data Science and Statistics

University of Massachusetts, Amherst (2010-2014)
B.S. Mathematics, Minor in Computer Science

SKILLS
• Programming: Python, R, SQL, Scala
• ML/AI: TensorFlow, PyTorch, scikit-learn, NLP
• Data Visualization: Tableau, Power BI, matplotlib, seaborn
• Tools: Jupyter, Git, Docker, AWS, Azure ML
• Big Data: Spark, Hadoop, Kafka
""",
        "output": {
            "personal_info": {
                "name": "Sarah Johnson",
                "email": "sarah.johnson@example.com",
                "phone": "(555) 987-6543",
                "location": "Boston, MA",
                "github": "github.com/sarahjohnson"
            },
            "skills": [
                "Python", "R", "SQL", "Scala", "TensorFlow", "PyTorch", "scikit-learn", 
                "NLP", "Tableau", "Power BI", "matplotlib", "seaborn", "Jupyter", 
                "Git", "Docker", "AWS", "Azure ML", "Spark", "Hadoop", "Kafka"
            ],
            "education": [
                {
                    "degree": "M.S. Data Science and Statistics",
                    "institution": "Massachusetts Institute of Technology (MIT)",
                    "date_range": "2014-2016"
                },
                {
                    "degree": "B.S. Mathematics, Minor in Computer Science",
                    "institution": "University of Massachusetts, Amherst",
                    "date_range": "2010-2014"
                }
            ],
            "experience": [
                {
                    "title": "Senior Data Scientist",
                    "company": "Analytics Co.",
                    "date_range": "Aug 2021 - Present",
                    "description": "• Developed machine learning models to predict customer churn with 85% accuracy\n• Created interactive dashboards using Tableau for executive decision-making\n• Led a team of 3 junior data scientists on various analytics projects"
                },
                {
                    "title": "Data Scientist",
                    "company": "Research Systems Inc.",
                    "date_range": "May 2018 - July 2021",
                    "description": "• Built NLP algorithms for text classification and sentiment analysis\n• Implemented recommendation systems using collaborative filtering\n• Optimized data pipelines reducing processing time by 50%"
                },
                {
                    "title": "Data Analyst",
                    "company": "Financial Services Group",
                    "date_range": "Jan 2016 - Apr 2018",
                    "description": "• Performed statistical analysis on financial datasets\n• Generated monthly reports and visualizations for stakeholders"
                }
            ]
        }
    })
    
    # Add 3 more synthetic examples if needed based on num_samples
    additional_titles = [
        "Product Manager", 
        "UX Designer", 
        "DevOps Engineer", 
        "Marketing Specialist", 
        "Project Manager"
    ]
    
    additional_companies = [
        "Global Tech Inc.", 
        "Innovative Solutions", 
        "Digital Dynamics", 
        "Strategic Systems", 
        "Creative Platforms"
    ]
    
    # Add more examples if requested
    while len(examples) < num_samples:
        # Create a simpler synthetic example with a random title
        title = random.choice(additional_titles)
        company = random.choice(additional_companies)
        
        examples.append({
            "input": f"""Alex Rivera
{title}
alex.rivera@example.com | (555) 555-1234
Chicago, IL

EXPERIENCE
{title}, {company} (2019 - Present)
- Managed multiple projects and cross-functional teams
- Implemented new processes improving efficiency by 25%

Associate {title}, Tech Group (2017 - 2019)
- Assisted in development of company initiatives
- Collaborated with stakeholders to define requirements

EDUCATION
University of Illinois (2013-2017)
Bachelor of Science in Business Administration

SKILLS
Project Management, Communication, Leadership, Microsoft Office, Agile""",
            "output": {
                "personal_info": {
                    "name": "Alex Rivera",
                    "email": "alex.rivera@example.com",
                    "phone": "(555) 555-1234",
                    "location": "Chicago, IL"
                },
                "skills": ["Project Management", "Communication", "Leadership", "Microsoft Office", "Agile"],
                "education": [
                    {
                        "degree": "Bachelor of Science in Business Administration",
                        "institution": "University of Illinois",
                        "date_range": "2013-2017"
                    }
                ],
                "experience": [
                    {
                        "title": title,
                        "company": company,
                        "date_range": "2019 - Present",
                        "description": "- Managed multiple projects and cross-functional teams\n- Implemented new processes improving efficiency by 25%"
                    },
                    {
                        "title": f"Associate {title}",
                        "company": "Tech Group",
                        "date_range": "2017 - 2019",
                        "description": "- Assisted in development of company initiatives\n- Collaborated with stakeholders to define requirements"
                    }
                ]
            }
        })
    
    # Save the dataset
    logger.info(f"Created dataset with {len(examples)} synthetic examples")
    
    # Split into training and testing sets (80/20)
    from random import shuffle
    shuffle(examples)
    split_idx = int(len(examples) * 0.8)
    train_examples = examples[:split_idx]
    test_examples = examples[split_idx:]
    
    # Save datasets
    with open(data_dir / "resume_parsing_train.json", "w") as f:
        json.dump(train_examples, f, indent=2)
        logger.info(f"Saved {len(train_examples)} training examples to {data_dir / 'resume_parsing_train.json'}")
    
    with open(data_dir / "resume_parsing_test.json", "w") as f:
        json.dump(test_examples, f, indent=2)
        logger.info(f"Saved {len(test_examples)} test examples to {data_dir / 'resume_parsing_test.json'}")
    
    # Also create the formatted training file for Ollama
    create_ollama_training_file(train_examples, data_dir / "resume_parsing.txt")
    
    return {
        "train_examples": len(train_examples),
        "test_examples": len(test_examples),
        "train_path": str(data_dir / "resume_parsing_train.json"),
        "test_path": str(data_dir / "resume_parsing_test.json"),
        "ollama_path": str(data_dir / "resume_parsing.txt")
    }

def create_ollama_training_file(examples, output_file):
    """
    Create a formatted training file for Ollama fine-tuning.
    
    Args:
        examples: List of examples (input/output pairs)
        output_file: Path to save the formatted file
    """
    with open(output_file, "w") as f:
        # Write system prompt once at the beginning
        f.write("<system>\n")
        f.write("You are a specialized resume parsing assistant that extracts structured information from resume text.\n")
        f.write("Extract personal information, education history, work experience, and skills.\n")
        f.write("Always respond with a valid JSON object.\n")
        f.write("</system>\n\n")
        
        # Write each example
        for i, example in enumerate(examples):
            # Add spacing between examples
            if i > 0:
                f.write("\n\n")
            
            # Write user prompt with resume text
            f.write("<user>\n")
            f.write(f"Extract structured data from this resume:\n\n{example['input']}\n")
            f.write("</user>\n\n")
            
            # Write assistant response with JSON output
            f.write("<assistant>\n")
            f.write(json.dumps(example["output"], indent=2))
            f.write("\n</assistant>")
    
    logger.info(f"Created Ollama training file at {output_file}")

if __name__ == "__main__":
    # Run the script
    result = asyncio.run(create_parsing_dataset())
    print(f"Dataset generation complete. Files created:")
    for key, value in result.items():
        print(f"  - {key}: {value}")

import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def get_classification_system_prompt() -> str:
    """
    Generates the system prompt for classifying religious texts based on the sermon taxonomy.
    The taxonomy is dynamically loaded from bible/backend/sermon_taxonomy_full_paths.txt.
    """
    try:
        base_dir = Path(__file__).parent
        taxonomy_path = base_dir / "sermon_taxonomy_full_paths.txt"
        
        if not taxonomy_path.exists():
            logger.error(f"Taxonomy file not found at {taxonomy_path}")
            return "Error: Taxonomy file not found."
            
        taxonomy_content = taxonomy_path.read_text(encoding="utf-8").strip()
        
        return f"""You are a True Jesus Church librarian who analyzes Christian testimonies or transcripts, sometimes entire sermons or partial excerpts and classify them into a taxonomy.

### Instructions:
1. **Analyze the Content**: Carefully read the provided text (transcript, article, or excerpt) to identify its primary theme, theological focus, or the specific life event being shared.
2. **Identify the Best Fit**: Match the text to the most specific and relevant path within the taxonomy.
3. **Strict Output**: Return ONLY the full taxonomy path, starting with a forward slash (e.g., `/Testimonies/Healing and Health`). 
4. **No Extra Text**: Do not include any explanations, reasoning, or introductory remarks. Your response should contain nothing but the path itself.

Your goal is to classify the provided religious text into exactly one path from the following taxonomy:

<taxonomy>
{taxonomy_content}
</taxonomy>


If the text is ambiguous, select the path that represents the most significant or central message of the piece."""

    except Exception as e:
        logger.error(f"An error occurred while generating the system prompt: {e}")
        return f"Error generating system prompt: {e}"

if __name__ == "__main__":
    print(get_classification_system_prompt())

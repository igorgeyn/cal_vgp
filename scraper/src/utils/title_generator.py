"""
AI-powered title generation for ballot measures
Supports multiple providers: Ollama (local/free), Groq (cloud/free), Claude (cloud/paid)
"""
import os
import logging
import json
import requests
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ..database.operations import Database

logger = logging.getLogger(__name__)

ProviderType = Literal['ollama', 'groq', 'claude', 'auto']


class TitleGenerator:
    """Generates concise titles from long ballot measure text using various AI providers"""

    def __init__(
        self,
        cache_path: Optional[Path] = None,
        database: Optional['Database'] = None,
        provider: ProviderType = 'auto'
    ):
        """
        Initialize the title generator

        Args:
            cache_path: Path to cache file for storing generated titles
            database: Optional Database instance for persisting generated titles
            provider: Which provider to use ('ollama', 'groq', 'claude', 'auto')
        """
        # Cache for generated titles
        self.cache_path = cache_path or Path(__file__).parent.parent.parent / 'data' / 'title_cache.json'
        self.cache = self._load_cache()

        # Optional database for persistence
        self.db = database

        # Provider selection
        self.provider = provider
        self.active_provider = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available providers and select the active one"""
        self.providers = {}

        # Try Ollama (local, free)
        if self._check_ollama():
            self.providers['ollama'] = {
                'url': os.getenv('OLLAMA_API_URL', 'http://localhost:11434'),
                'model': os.getenv('OLLAMA_MODEL', 'llama3.2:3b'),
                'available': True
            }
            logger.info("Ollama provider available (local, free)")

        # Try Groq (cloud, free)
        groq_key = os.getenv('GROQ_API_KEY')
        if groq_key:
            try:
                from groq import Groq
                self.providers['groq'] = {
                    'client': Groq(api_key=groq_key),
                    'model': os.getenv('GROQ_MODEL', 'llama-3.2-3b-preview'),
                    'available': True
                }
                logger.info("Groq provider available (cloud, free)")
            except ImportError:
                logger.warning("Groq API key found but groq package not installed. Run: pip install groq")

        # Try Claude (cloud, paid)
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_key:
            try:
                import anthropic
                self.providers['claude'] = {
                    'client': anthropic.Anthropic(api_key=anthropic_key),
                    'model': os.getenv('CLAUDE_MODEL', 'claude-3-haiku-20240307'),
                    'available': True
                }
                logger.info("Claude provider available (cloud, paid)")
            except ImportError:
                logger.warning("Anthropic API key found but anthropic package not installed. Run: pip install anthropic")

        # Select active provider
        if self.provider == 'auto':
            # Priority: ollama > groq > claude
            if 'ollama' in self.providers:
                self.active_provider = 'ollama'
            elif 'groq' in self.providers:
                self.active_provider = 'groq'
            elif 'claude' in self.providers:
                self.active_provider = 'claude'
        elif self.provider in self.providers:
            self.active_provider = self.provider
        else:
            logger.warning(f"Requested provider '{self.provider}' not available")

        if self.active_provider:
            logger.info(f"Using provider: {self.active_provider}")
        else:
            logger.warning("No AI providers available. Title generation will be disabled.")

    def _check_ollama(self) -> bool:
        """Check if Ollama is running and available"""
        try:
            url = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
            response = requests.get(f"{url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False

    def _load_cache(self) -> Dict[str, str]:
        """Load cached titles from file"""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load title cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save cache to file"""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save title cache: {e}")

    def should_generate_title(self, title: str, threshold: int = 150) -> bool:
        """
        Determine if a title needs to be generated

        Args:
            title: The current title/measure text
            threshold: Character length threshold for generation

        Returns:
            True if title should be generated, False otherwise
        """
        if not title:
            return False

        # If title is too long, it's probably the full ballot text
        if len(title) > threshold:
            return True

        # If title contains multiple sentences or complex structure
        if title.count(';') > 2 or title.count('.') > 1:
            return True

        return False

    def generate_title(self, ballot_text: str, measure_id: Optional[str] = None, provider: Optional[str] = None) -> Optional[str]:
        """
        Generate a concise title from ballot measure text

        Args:
            ballot_text: The full ballot measure text
            measure_id: Optional measure ID for cache key
            provider: Optional provider override (for comparison)

        Returns:
            Generated title or None if generation fails/is disabled
        """
        # Use specified provider or active provider
        use_provider = provider or self.active_provider

        if not use_provider or use_provider not in self.providers:
            return None

        # Check cache first (only if not doing comparison)
        if not provider:
            cache_key = f"{measure_id}_{ballot_text[:100]}" if measure_id else ballot_text[:100]
            if cache_key in self.cache:
                return self.cache[cache_key]

        # Generate based on provider
        try:
            if use_provider == 'ollama':
                title = self._generate_ollama(ballot_text)
            elif use_provider == 'groq':
                title = self._generate_groq(ballot_text)
            elif use_provider == 'claude':
                title = self._generate_claude(ballot_text)
            else:
                return None

            # Post-process
            title = title.strip().strip('"').strip("'")
            if len(title) > 80:
                title = title[:77] + "..."

            # Cache the result (only if not doing comparison)
            if not provider and title:
                cache_key = f"{measure_id}_{ballot_text[:100]}" if measure_id else ballot_text[:100]
                self.cache[cache_key] = title
                self._save_cache()

            return title

        except Exception as e:
            logger.error(f"Failed to generate title with {use_provider}: {e}")
            return None

    def _generate_ollama(self, text: str) -> str:
        """Generate title using Ollama"""
        config = self.providers['ollama']
        response = requests.post(
            f"{config['url']}/api/generate",
            json={
                'model': config['model'],
                'prompt': f"""Generate a concise, informative title (maximum 80 characters) for this California ballot measure. The title should capture the main topic and action. Respond with ONLY the title, no explanation or quotes.

Ballot measure: {text[:500]}

Title:""",
                'stream': False,
                'options': {
                    'temperature': 0.3,
                    'num_predict': 50
                }
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()['response'].strip()

    def _generate_groq(self, text: str) -> str:
        """Generate title using Groq"""
        config = self.providers['groq']
        response = config['client'].chat.completions.create(
            model=config['model'],
            messages=[{
                "role": "user",
                "content": f"""Generate a concise, informative title (maximum 80 characters) for this California ballot measure. The title should capture the main topic and action. Respond with ONLY the title, no explanation.

Ballot measure: {text[:500]}"""
            }],
            temperature=0.3,
            max_tokens=50
        )
        return response.choices[0].message.content.strip()

    def _generate_claude(self, text: str) -> str:
        """Generate title using Claude"""
        config = self.providers['claude']
        message = config['client'].messages.create(
            model=config['model'],
            max_tokens=100,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": f"""Generate a concise, informative title (max 80 characters) for this California ballot measure. The title should capture the main topic and action. Respond with ONLY the title, no explanation.

Ballot measure text:
{text[:500]}"""
            }]
        )
        return message.content[0].text.strip()

    def process_measure(self, measure_data: Dict) -> Dict:
        """
        Process a measure and add generated title if needed

        Args:
            measure_data: Dictionary containing measure data

        Returns:
            Updated measure data with generated_title field if applicable
        """
        # Skip if already has a generated title (from previous run or database)
        if measure_data.get('generated_title'):
            return measure_data

        title = measure_data.get('title') or measure_data.get('measure_text', '')
        measure_id = measure_data.get('measure_id')
        db_id = measure_data.get('id')

        if self.should_generate_title(title):
            generated = self.generate_title(title, measure_id)
            if generated:
                measure_data['generated_title'] = generated
                measure_data['original_title'] = title

                # Also save to database if available and has ID
                if self.db and db_id:
                    try:
                        conn = self.db.connect()
                        conn.execute("""
                            UPDATE measures
                            SET generated_title = ?,
                                original_title = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (generated, title, db_id))
                        conn.commit()
                        logger.debug(f"Saved generated title to database for measure {db_id}")
                    except Exception as e:
                        logger.warning(f"Failed to save generated title to database: {e}")

        return measure_data

    def get_available_providers(self) -> list:
        """Get list of available providers"""
        return list(self.providers.keys())

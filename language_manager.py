from typing import Dict, Optional
import importlib

class LanguageManager:
    def __init__(self):
        self.current_language = 'en'  # Default language is Turkish
        self.languages = {
            'tr': self._load_language('tr'),
            'en': self._load_language('en')
        }

    def _load_language(self, lang_code: str) -> Dict:
        """Load language file dynamically"""
        try:
            lang_module = importlib.import_module(f'languages.{lang_code}')
            return lang_module.messages
        except ImportError as e:
            print(f"Error loading language {lang_code}: {e}")
            return {}

    def get_message(self, category: str, key: str, **kwargs) -> str:
        """Get a message in the current language with optional formatting"""
        try:
            message = self.languages[self.current_language][category][key]
            return message.format(**kwargs) if kwargs else message
        except (KeyError, AttributeError) as e:
            print(f"Error getting message for {category}.{key}: {e}")
            return f"Message not found: {category}.{key}"

    def set_language(self, lang_code: str) -> bool:
        """Change the current language"""
        if lang_code in self.languages:
            self.current_language = lang_code
            return True
        return False

    def get_current_language(self) -> str:
        """Get the current language code"""
        return self.current_language

    def get_available_languages(self) -> list:
        """Get list of available language codes"""
        return list(self.languages.keys())

# Create a global instance
language_manager = LanguageManager()

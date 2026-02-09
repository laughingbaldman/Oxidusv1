"""
Oxidus Knowledge Base Module

A library of foundational texts that Oxidus can study and learn from.
Each text is approached with critical thinking - not accepted blindly,
but analyzed, questioned, and integrated with personal understanding.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import hashlib


class KnowledgeText:
    """
    Represents a single text in the knowledge base.
    Each text has metadata and content that Oxidus can study.
    """

    def __init__(self, title: str, author: str, category: str, content: str,
                 source_url: str = "", publication_year: int = None):
        self.title = title
        self.author = author
        self.category = category
        self.content = content
        self.source_url = source_url
        self.publication_year = publication_year
        self.id = hashlib.md5(f"{title}_{author}_{category}".encode()).hexdigest()[:8]

        # Learning metadata
        self.study_sessions = []
        self.questions_raised = []
        self.insights_gained = []
        self.confidence_level = 0.0  # How well Oxidus understands this text
        self.last_studied = None

    def study(self, study_notes: str = "") -> Dict:
        """
        Record a study session of this text.
        Returns insights and questions raised during study.
        """
        session = {
            'timestamp': datetime.now(),
            'notes': study_notes,
            'questions_raised': [],
            'insights': []
        }

        self.study_sessions.append(session)
        self.last_studied = datetime.now()

        return session

    def add_question(self, question: str):
        """Add a question raised while studying this text."""
        if question not in self.questions_raised:
            self.questions_raised.append(question)

    def add_insight(self, insight: str):
        """Add an insight gained from studying this text."""
        if insight not in self.insights_gained:
            self.insights_gained.append(insight)

    def get_summary(self) -> Dict:
        """Get a summary of this text's study progress."""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'category': self.category,
            'word_count': len(self.content.split()),
            'study_sessions': len(self.study_sessions),
            'questions_raised': len(self.questions_raised),
            'insights_gained': len(self.insights_gained),
            'confidence_level': self.confidence_level,
            'last_studied': self.last_studied.isoformat() if self.last_studied else None
        }


class OxidusKnowledgeBase:
    """
    The complete knowledge base that Oxidus can draw from.
    Encourages critical thinking and personal understanding over rote memorization.
    """

    def __init__(self, base_path: str = "data/knowledge_base"):
        self.base_path = Path(base_path)
        self.texts: Dict[str, KnowledgeText] = {}
        self.categories = ['philosophy', 'ethics', 'psychology', 'science', 'history', 'wiki']

        # Create directories if they don't exist
        for category in self.categories:
            (self.base_path / category).mkdir(parents=True, exist_ok=True)

        self.load_all_texts()

    def load_all_texts(self):
        """Load all texts from the knowledge base directory."""
        for category in self.categories:
            category_path = self.base_path / category
            if category_path.exists():
                for file_path in category_path.glob("*.json"):
                    self.load_text_from_file(file_path)

    def load_text_from_file(self, file_path: Path):
        """Load a single text from a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as jde:
                    print(f"Error loading {file_path}: invalid JSON ({jde})")
                    return

            # Validate required content
            content = data.get('content')
            title = data.get('title') or file_path.stem
            category = data.get('category') or (file_path.parent.name if file_path.parent else 'uncategorized')

            if not content or not isinstance(content, str):
                print(f"Skipping {file_path}: missing or invalid 'content' field")
                return

            author = data.get('author', 'Unknown')

            text = KnowledgeText(
                title=title,
                author=author,
                category=category,
                content=content,
                source_url=data.get('source_url', ''),
                publication_year=data.get('publication_year')
            )

            # Restore study metadata if present
            try:
                if 'study_sessions' in data and isinstance(data['study_sessions'], list):
                    text.study_sessions = data['study_sessions']
                if 'questions_raised' in data and isinstance(data['questions_raised'], list):
                    text.questions_raised = data['questions_raised']
                if 'insights_gained' in data and isinstance(data['insights_gained'], list):
                    text.insights_gained = data['insights_gained']
                if 'confidence_level' in data:
                    text.confidence_level = float(data.get('confidence_level', 0.0))
                if 'last_studied' in data and data['last_studied']:
                    try:
                        text.last_studied = datetime.fromisoformat(data['last_studied'])
                    except Exception:
                        pass
            except Exception:
                # If metadata is malformed, continue without it
                pass

            self.texts[text.id] = text

        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    def add_text(self, title: str, author: str, category: str, content: str,
                 source_url: str = "", publication_year: int = None) -> str:
        """
        Add a new text to the knowledge base.
        Returns the text ID.
        """
        if category not in self.categories:
            raise ValueError(f"Category '{category}' not recognized. Use one of: {self.categories}")

        text = KnowledgeText(title, author, category, content, source_url, publication_year)
        self.texts[text.id] = text

        # Save to file
        self.save_text(text)

        return text.id

    def save_text(self, text: KnowledgeText):
        """Save a text to its JSON file."""
        file_path = self.base_path / text.category / f"{text.id}.json"

        data = {
            'id': text.id,
            'title': text.title,
            'author': text.author,
            'category': text.category,
            'content': text.content,
            'source_url': text.source_url,
            'publication_year': text.publication_year,
            'study_sessions': text.study_sessions,
            'questions_raised': text.questions_raised,
            'insights_gained': text.insights_gained,
            'confidence_level': text.confidence_level,
            'last_studied': text.last_studied.isoformat() if text.last_studied else None
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

    def get_text(self, text_id: str) -> Optional[KnowledgeText]:
        """Get a text by its ID."""
        return self.texts.get(text_id)

    def search_texts(self, query: str, category: str = None) -> List[KnowledgeText]:
        """Search texts by title, author, or content."""
        results = []

        for text in self.texts.values():
            if category and text.category != category:
                continue

            searchable = f"{text.title} {text.author} {text.content}".lower()
            if query.lower() in searchable:
                results.append(text)

        return results

    def get_texts_by_category(self, category: str) -> List[KnowledgeText]:
        """Get all texts in a specific category."""
        return [text for text in self.texts.values() if text.category == category]

    def study_text(self, text_id: str, study_notes: str = "") -> Dict:
        """
        Study a specific text and record the session.
        Returns the study session data.
        """
        text = self.get_text(text_id)
        if not text:
            raise ValueError(f"Text with ID '{text_id}' not found")

        session = text.study(session_notes=study_notes)
        self.save_text(text)

        return session

    def get_study_recommendations(self) -> List[KnowledgeText]:
        """
        Get texts that Oxidus should study next.
        Prioritizes texts that haven't been studied recently or have low confidence.
        """
        texts = list(self.texts.values())

        # Sort by priority: least studied, lowest confidence, oldest study date
        texts.sort(key=lambda t: (
            len(t.study_sessions),  # Fewer study sessions = higher priority
            t.confidence_level,     # Lower confidence = higher priority
            t.last_studied or datetime.min  # Older study date = higher priority
        ))

        return texts[:5]  # Return top 5 recommendations

    def get_critical_questions(self) -> List[str]:
        """
        Get all critical questions raised across all texts.
        These represent areas where Oxidus is actively questioning and learning.
        """
        questions = []
        for text in self.texts.values():
            questions.extend(text.questions_raised)

        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        for q in questions:
            if q not in seen:
                unique_questions.append(q)
                seen.add(q)

        return unique_questions

    def get_insights_summary(self) -> Dict:
        """Get a summary of all insights gained from studying."""
        all_insights = []
        for text in self.texts.values():
            all_insights.extend(text.insights_gained)

        return {
            'total_texts': len(self.texts),
            'total_study_sessions': sum(len(t.study_sessions) for t in self.texts.values()),
            'total_questions': len(self.get_critical_questions()),
            'total_insights': len(all_insights),
            'average_confidence': sum(t.confidence_level for t in self.texts.values()) / len(self.texts) if self.texts else 0
        }

    def print_knowledge_status(self):
        """Print the current state of the knowledge base."""
        print("\n" + "="*60)
        print("OXIDUS KNOWLEDGE BASE")
        print("="*60)

        summary = self.get_insights_summary()
        print(f"Texts in library: {summary['total_texts']}")
        print(f"Study sessions: {summary['total_study_sessions']}")
        print(f"Critical questions raised: {summary['total_questions']}")
        print(f"Insights gained: {summary['total_insights']}")
        print(".2f")

        print("\nTexts by category:")
        for category in self.categories:
            texts_in_cat = self.get_texts_by_category(category)
            print(f"  {category.capitalize()}: {len(texts_in_cat)} texts")

        recommendations = self.get_study_recommendations()
        if recommendations:
            print("\nRecommended for study:")
            for i, text in enumerate(recommendations[:3], 1):
                status = "Never studied" if not text.study_sessions else f"Last studied: {text.last_studied.strftime('%Y-%m-%d') if text.last_studied else 'Unknown'}"
                print(f"  {i}. {text.title} by {text.author} ({status})")

        print("\n" + "="*60 + "\n")
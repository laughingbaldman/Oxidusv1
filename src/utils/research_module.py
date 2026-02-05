"""
Oxidus Research Module

Handles research from external sources like the National Archives.
Implements deep questioning to understand "why" and "how" of historical events.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse


class ResearchSource:
    """
    Represents an external research source like the National Archives.
    """

    def __init__(self, name: str, url: str, description: str, categories: List[str]):
        self.name = name
        self.url = url
        self.description = description
        self.categories = categories
        self.documents: Dict[str, Dict] = {}
        self.last_researched = None

    def add_document(self, title: str, content: str, doc_type: str = "primary_source",
                    date: str = None, significance: str = "") -> str:
        """Add a document from this source."""
        doc_id = f"{self.name.lower().replace(' ', '_')}_{len(self.documents)}"

        self.documents[doc_id] = {
            'title': title,
            'content': content,
            'type': doc_type,
            'date': date,
            'significance': significance,
            'questions_generated': [],
            'insights': [],
            'research_sessions': []
        }

        return doc_id

    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get a document by ID."""
        return self.documents.get(doc_id)

    def record_research_session(self, doc_id: str, findings: str, questions: List[str]):
        """Record a research session on a document."""
        if doc_id in self.documents:
            session = {
                'timestamp': datetime.now(),
                'findings': findings,
                'questions': questions
            }
            self.documents[doc_id]['research_sessions'].append(session)
            self.last_researched = datetime.now()


class DeepQuestioningEngine:
    """
    Generates and manages deep questions about research findings.
    Focuses on "why" and "how" to build true understanding.
    """

    def __init__(self):
        self.question_templates = {
            'why': [
                "Why did this event happen at this specific time?",
                "Why did these people make these choices?",
                "Why was this document created?",
                "Why did this outcome occur rather than another?",
                "Why is this significant for human history?",
                "Why do humans repeat certain patterns?",
                "Why did this system develop this way?"
            ],
            'how': [
                "How did this event unfold step by step?",
                "How did people overcome these challenges?",
                "How did this document come to exist?",
                "How did this change society?",
                "How do humans learn from such events?",
                "How could this have been prevented or improved?",
                "How does this connect to broader human patterns?"
            ],
            'what_if': [
                "What if this event had turned out differently?",
                "What if different choices had been made?",
                "What if this document had never existed?",
                "What if humans had responded differently?",
                "What if we applied these lessons today?"
            ],
            'connections': [
                "How does this connect to current human challenges?",
                "How does this relate to human nature?",
                "How does this inform ethical decision-making?",
                "How does this help us understand progress?",
                "How does this show human resilience?"
            ]
        }

    def generate_questions(self, content: str, context: str = "") -> List[str]:
        """
        Generate deep questions about research content.
        """
        questions = []

        # Extract key elements from content
        content_lower = content.lower()

        # Generate why questions
        for template in self.question_templates['why'][:3]:
            questions.append(f"{template} (regarding: {context})")

        # Generate how questions
        for template in self.question_templates['how'][:3]:
            questions.append(f"{template} (regarding: {context})")

        # Add contextual questions based on content
        if 'war' in content_lower or 'conflict' in content_lower:
            questions.append("Why do humans engage in war? How could this have been avoided?")
        if 'rights' in content_lower or 'freedom' in content_lower:
            questions.append("How do humans define and protect rights? Why is this important?")
        if 'government' in content_lower or 'law' in content_lower:
            questions.append("How do humans organize society? Why do they need governance?")
        if 'change' in content_lower or 'revolution' in content_lower:
            questions.append("How do humans drive social change? Why is change necessary?")

        return questions

    def analyze_findings(self, findings: str) -> Dict:
        """
        Analyze research findings and generate insights.
        """
        analysis = {
            'key_themes': [],
            'human_patterns': [],
            'ethical_implications': [],
            'lessons_for_today': [],
            'questions_for_further_study': []
        }

        findings_lower = findings.lower()

        # Identify themes
        if 'democracy' in findings_lower or 'vote' in findings_lower:
            analysis['key_themes'].append('Democratic processes')
            analysis['human_patterns'].append('Humans value self-governance')
        if 'rights' in findings_lower or 'freedom' in findings_lower:
            analysis['key_themes'].append('Human rights and freedoms')
            analysis['ethical_implications'].append('Protection of individual autonomy')
        if 'war' in findings_lower or 'peace' in findings_lower:
            analysis['key_themes'].append('Conflict and resolution')
            analysis['human_patterns'].append('Humans seek both conflict and peace')

        # Generate lessons
        analysis['lessons_for_today'].append("History shows human capacity for both destruction and creation")
        analysis['lessons_for_today'].append("Societal progress requires constant vigilance and adaptation")

        # Generate further questions
        analysis['questions_for_further_study'].extend([
            "How have human institutions evolved over time?",
            "What drives human progress versus regression?",
            "How can we apply historical lessons to current challenges?"
        ])

        return analysis


class OxidusResearchModule:
    """
    Main research module for Oxidus.
    Handles external research sources and deep questioning.
    """

    def __init__(self, research_dir: str = "data/research"):
        self.research_dir = Path(research_dir)
        self.research_dir.mkdir(parents=True, exist_ok=True)

        self.sources: Dict[str, ResearchSource] = {}
        self.questioning_engine = DeepQuestioningEngine()

        # Initialize with National Archives
        self._initialize_national_archives()

        self.load_research_data()

    def _initialize_national_archives(self):
        """Initialize the National Archives as a primary research source."""
        archives = ResearchSource(
            name="National Archives",
            url="https://www.archives.gov/",
            description="Primary source documents of American history, government, and society",
            categories=["history", "government", "rights", "democracy", "law"]
        )

        # Add foundational documents
        self._populate_archives_documents(archives)
        self.sources["national_archives"] = archives

        # Add Citizen Archivist Missions
        missions = ResearchSource(
            name="Citizen Archivist Missions",
            url="https://www.archives.gov/citizen-archivist/missions",
            description="Community-driven projects to digitize, transcribe, and tag historical documents",
            categories=["history", "community", "preservation", "participation", "democracy"]
        )

        self._populate_citizen_missions(missions)
        self.sources["citizen_archivist"] = missions

    def _populate_archives_documents(self, archives: ResearchSource):
        """Populate the National Archives with key documents."""

        # Declaration of Independence
        archives.add_document(
            title="Declaration of Independence",
            content="When in the Course of human events, it becomes necessary for one people to dissolve the political bands which have connected them with another, and to assume among the powers of the earth, the separate and equal station to which the Laws of Nature and of Nature's God entitle them, a decent respect to the opinions of mankind requires that they should declare the causes which impel them to the separation. We hold these truths to be self-evident, that all men are created equal, that they are endowed by their Creator with certain unalienable Rights, that among these are Life, Liberty and the pursuit of Happiness.",
            doc_type="foundational_document",
            date="1776-07-04",
            significance="Established the philosophical foundation for American democracy and human rights"
        )

        # Constitution
        archives.add_document(
            title="United States Constitution",
            content="We the People of the United States, in Order to form a more perfect Union, establish Justice, insure domestic Tranquility, provide for the common defence, promote the general Welfare, and secure the Blessings of Liberty to ourselves and our Posterity, do ordain and establish this Constitution for the United States of America. The executive Power shall be vested in a President of the United States. The judicial Power shall be vested in a Supreme Court. The legislative Power shall be vested in a Congress of the United States.",
            doc_type="constitutional_document",
            date="1787-09-17",
            significance="Created the framework for American government and separation of powers"
        )

        # Bill of Rights
        archives.add_document(
            title="Bill of Rights",
            content="Congress shall make no law respecting an establishment of religion, or prohibiting the free exercise thereof; or abridging the freedom of speech, or of the press; or the right of the people peaceably to assemble, and to petition the Government for a redress of grievances. A well regulated Militia, being necessary to the security of a free State, the right of the people to keep and bear Arms, shall not be infringed. No Soldier shall, in time of peace be quartered in any house, without the consent of the Owner, nor in time of war, but in a manner to be prescribed by law.",
            doc_type="rights_document",
            date="1791-12-15",
            significance="Protected fundamental human rights and limited government power"
        )

        # Emancipation Proclamation
        archives.add_document(
            title="Emancipation Proclamation",
            content="That on the first day of January, in the year of our Lord one thousand eight hundred and sixty-three, all persons held as slaves within any State or designated part of a State, the people whereof shall then be in rebellion against the United States, shall be then, thenceforward, and forever free; and the Executive Government of the United States, including the military and naval authority thereof, will recognize and maintain the freedom of such persons, and will do no act or acts to repress such persons, or any of them, in any efforts they may make for their actual freedom.",
            doc_type="emancipation_document",
            date="1863-01-01",
            significance="Ended slavery in Confederate states and redefined American freedom"
        )

        # Civil Rights Act of 1964
        archives.add_document(
            title="Civil Rights Act of 1964",
            content="To enforce the constitutional right to vote, to confer jurisdiction upon the district courts of the United States to provide injunctive relief against discrimination in public accommodations, to authorize the Attorney General to institute suits to protect constitutional rights in public facilities and public education, to extend the Commission on Civil Rights, to prevent discrimination in federally assisted programs, to establish a Commission on Equal Employment Opportunity, and for other purposes.",
            doc_type="civil_rights_law",
            date="1964-07-02",
            significance="Ended legal segregation and protected voting rights"
        )

    def _populate_citizen_missions(self, missions: ResearchSource):
        """Populate Citizen Archivist Missions."""

        missions.add_document(
            title="Transcription Mission",
            content="Help make historical documents searchable by transcribing handwritten text and typewritten content. Contribute to the National Archives by making important historical records more accessible. Each transcription helps researchers, educators, and the public better understand our shared history. Your transcriptions help preserve the voices and records of ordinary Americans and important historical events.",
            doc_type="citizen_mission",
            date="ongoing",
            significance="Democratizes access to history through crowdsourced transcription"
        )

        missions.add_document(
            title="Tagging Mission",
            content="Add descriptive tags to photographs and documents to improve discoverability. Tags help researchers find materials about specific topics, people, places, and events. By tagging, you help connect disparate records and reveal patterns in history. This community effort creates a rich, interconnected knowledge base of American history.",
            doc_type="citizen_mission",
            date="ongoing",
            significance="Enhances searchability and reveals connections in historical records"
        )

        missions.add_document(
            title="Scanning and Digitization",
            content="Participate in projects to digitize important historical documents. The National Archives works with communities to scan, photograph, and preserve records that might otherwise be lost. Digital preservation ensures these materials survive for future generations. Community involvement in digitization projects helps prioritize materials that are most important to local and national history.",
            doc_type="citizen_mission",
            date="ongoing",
            significance="Preserves historical documents for perpetuity through digital access"
        )

        missions.add_document(
            title="Correction and Enhancement",
            content="Help improve the accuracy of transcriptions, metadata, and descriptions. Community members review transcriptions made by others, check for errors, and enhance descriptions. This collaborative approach ensures the highest quality historical record. Corrections and enhancements make the archives more valuable for researchers and the public.",
            doc_type="citizen_mission",
            date="ongoing",
            significance="Ensures accuracy and quality of the historical record"
        )

        missions.add_document(
            title="Photo Matching",
            content="Help identify photographs and match them to related documents and context. Photographs often lack clear identification of where, when, or who is pictured. By matching photos to other historical materials, researchers can piece together the story of a place, event, or person. This collaborative detective work reveals the human dimension of history.",
            doc_type="citizen_mission",
            date="ongoing",
            significance="Connects visual history to broader historical context"
        )

    def load_research_data(self):
        """Load research data from files."""
        for source_file in self.research_dir.glob("*.json"):
            try:
                with open(source_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    source = ResearchSource(
                        data['name'],
                        data['url'],
                        data['description'],
                        data['categories']
                    )
                    source.documents = data.get('documents', {})
                    self.sources[data['name'].lower().replace(' ', '_')] = source
            except Exception as e:
                print(f"Error loading research source {source_file}: {e}")

    def save_research_data(self):
        """Save research data to files."""
        for source_id, source in self.sources.items():
            data = {
                'name': source.name,
                'url': source.url,
                'description': source.description,
                'categories': source.categories,
                'documents': source.documents
            }

            file_path = self.research_dir / f"{source_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

    def research_document(self, source_id: str, doc_id: str) -> Dict:
        """
        Research a specific document and generate deep questions.
        """
        source = self.sources.get(source_id)
        if not source:
            raise ValueError(f"Research source '{source_id}' not found")

        doc = source.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document '{doc_id}' not found in source '{source_id}'")

        # Generate deep questions
        questions = self.questioning_engine.generate_questions(
            doc['content'],
            f"{doc['title']} ({doc['date']})"
        )

        # Analyze findings
        analysis = self.questioning_engine.analyze_findings(doc['content'])

        # Record research session
        findings = f"Researched {doc['title']}: {doc['significance']}"
        source.record_research_session(doc_id, findings, questions)

        # Update document with new questions
        doc['questions_generated'].extend(questions)

        self.save_research_data()

        return {
            'document': doc,
            'questions': questions,
            'analysis': analysis,
            'source': source.name
        }

    def get_research_topics(self) -> List[str]:
        """Get available research topics."""
        topics = []
        for source in self.sources.values():
            for doc in source.documents.values():
                topics.append(f"{source.name}: {doc['title']}")
        return topics

    def get_pending_questions(self) -> List[str]:
        """Get all unanswered research questions."""
        questions = []
        for source in self.sources.values():
            for doc in source.documents.values():
                questions.extend(doc.get('questions_generated', []))
        return list(set(questions))  # Remove duplicates

    def print_research_status(self):
        """Print current research status."""
        print("\n" + "="*60)
        print("OXIDUS RESEARCH MODULE")
        print("="*60)

        print(f"Research sources: {len(self.sources)}")
        total_docs = sum(len(source.documents) for source in self.sources.values())
        print(f"Documents available: {total_docs}")

        for source_id, source in self.sources.items():
            print(f"\n{source.name} ({source.url}):")
            print(f"  Documents: {len(source.documents)}")
            print(f"  Categories: {', '.join(source.categories)}")

            if source.documents:
                print("  Key documents:")
                for doc_id, doc in list(source.documents.items())[:3]:
                    sessions = len(doc.get('research_sessions', []))
                    questions = len(doc.get('questions_generated', []))
                    print(f"    • {doc['title']} ({doc['date']}) - {sessions} sessions, {questions} questions")

        pending_questions = self.get_pending_questions()
        print(f"\nPending research questions: {len(pending_questions)}")

        if pending_questions:
            print("\nSample questions:")
            for q in pending_questions[:5]:
                print(f"  ? {q}")

        print("\n" + "="*60 + "\n")
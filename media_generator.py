"""Media Content Generator for EduRipple - Audio, Flashcards, Video and Visual Content"""

import os
import json
import logging
import uuid
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Try to import TTS library (fallback)
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("gTTS not installed. Using ElevenLabs or limited audio generation.")

# Try to import ElevenLabs
try:
    from elevenlabs import ElevenLabs, VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logger.warning("ElevenLabs not installed. Audio will use gTTS fallback.")

# ElevenLabs configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Pre-made voice IDs from ElevenLabs (free tier voices)
ELEVENLABS_VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",      # Friendly, clear, American female
    "drew": "29vD33N1CtxCmqQRPOHJ",         # Warm, confident male  
    "clyde": "2EiwWnXFnvU5JabPnv8n",        # Deep, authoritative male
    "paul": "5Q0t7uMcjvnagumLfvZi",          # Narration, male
    "domi": "AZnzlk1XvdvUeBnXmlld",          # Strong, expressive female
    "dave": "CYw3kZ02Hs0563khs1Fj",          # British, conversational
    "fin": "D38z5RcWu1voky8WS1ja",           # Irish, friendly male
    "sarah": "EXAVITQu4vr4xnSDxMaL",         # Soft, news reporter female
    "antoni": "ErXwobaYiN019PkySvjV",        # Well-rounded, male
    "thomas": "GBv7mTt0atIp3Br8iCZE",        # Calm, American male
    "charlie": "IKne3meq5aSn9XLyUdCD",       # Natural, Australian male
    "emily": "LcfcDJNUP1GQjkzn1xUU",         # Calm, American female
    "elli": "MF3mGyEYCl7XYWbV9V6O",          # Emotional range female
    "callum": "N2lVS1w4EtoT3dr4eOWO",        # Intense, American male
    "patrick": "ODq5zmih8GrVes37Dizd",       # Shouty, male
    "harry": "SOYHLrjzK2X1ezoPC6cr",         # Anxious, British male
    "liam": "TX3LPaxmHKxFdv7VOQHJ",          # Neutral, American male
    "dorothy": "ThT5KcBeYPX3keUQqHPh",       # Pleasant, British female
    "josh": "TxGEqnHWrfWFTfGW9XjX",          # Deep, American male
    "arnold": "VR6AewLTigWG4xSOukaG",        # Crisp, American male
    "charlotte": "XB0fDUnXU5powFXDhCwa",     # Seductive, Swedish female
    "matilda": "XrExE9yKIg1WjnnlVkGX",       # Warm, American female
    "matthew": "Yko7PKs6WkxO6TKIWo5S",       # Audiobook male
    "james": "ZQe5CZNOzWyzPSCn5a3c",         # Australian male
    "joseph": "Zlb1dXrM653N07WRdFW3",        # British male
    "adam": "pNInz6obpgDQGcFmaJgB",          # Deep, American male
    "nicole": "piTKgcLEGmPE4e6mEKli",        # Whisper, American female
    "glinda": "z9fAnlkpzviPz146aGWa",        # Witch, American female
    "giovanni": "zcAOhNBS3c14rBihAFp1",      # Italian accent male
    "mimi": "zrHiDhphv9ZnVXBqCLjz",          # Childish, Swedish female
}

# Try to import video libraries
try:
    from moviepy import (
        AudioFileClip, ImageClip, 
        concatenate_videoclips
    )
    from PIL import Image, ImageDraw, ImageFont
    MOVIEPY_AVAILABLE = True
    logger.info("MoviePy loaded successfully")
except ImportError as e:
    try:
        # Fallback to old import style for moviepy 1.x
        from moviepy.editor import (
            AudioFileClip, concatenate_videoclips, ImageClip
        )
        from PIL import Image, ImageDraw, ImageFont
        MOVIEPY_AVAILABLE = True
        logger.info("MoviePy (legacy) loaded successfully")
    except ImportError:
        MOVIEPY_AVAILABLE = False
        logger.warning(f"MoviePy not installed or import error: {e}. Video generation will be limited.")

# Directory for generated media
MEDIA_DIR = os.path.join(os.path.dirname(__file__), 'static', 'generated_media')
os.makedirs(MEDIA_DIR, exist_ok=True)


class AudioGenerator:
    """Generate audio content for educational purposes"""
    
    SPEED_SETTINGS = {
        'slow': {'slow': True},
        'normal': {'slow': False},
        'fast': {'slow': False}  # gTTS doesn't have fast, we'll note this
    }
    
    LANGUAGES = {
        'english': 'en',
        'kiswahili': 'sw',
        'french': 'fr'
    }
    
    @staticmethod
    def generate_reading_audio(text: str, speed: str = 'normal', language: str = 'english') -> Dict[str, Any]:
        """
        Generate audio of text being read at specified speed.
        Useful for listening comprehension exercises.
        
        Args:
            text: The text to convert to speech
            speed: 'slow', 'normal', or 'fast'
            language: 'english', 'kiswahili', or 'french'
        
        Returns:
            Dict with success status and file URL
        """
        if not GTTS_AVAILABLE:
            return {
                "success": False,
                "error": "Text-to-speech is not available. Please install gTTS."
            }
        
        if not text or len(text.strip()) < 5:
            return {
                "success": False,
                "error": "Text is too short for audio generation."
            }
        
        try:
            # Get language code
            lang_code = AudioGenerator.LANGUAGES.get(language.lower(), 'en')
            
            # Get speed setting
            speed_config = AudioGenerator.SPEED_SETTINGS.get(speed.lower(), {'slow': False})
            
            # Generate unique filename
            file_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_{speed}_{timestamp}_{file_id}.mp3"
            filepath = os.path.join(MEDIA_DIR, filename)
            
            # Create audio
            tts = gTTS(text=text, lang=lang_code, slow=speed_config['slow'])
            tts.save(filepath)
            
            # Calculate approximate duration (rough estimate: 150 words per minute normal, 100 slow)
            word_count = len(text.split())
            if speed == 'slow':
                duration_seconds = (word_count / 100) * 60
            else:
                duration_seconds = (word_count / 150) * 60
            
            return {
                "success": True,
                "file_url": f"/static/generated_media/{filename}",
                "filename": filename,
                "speed": speed,
                "language": language,
                "word_count": word_count,
                "estimated_duration": f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}",
                "text_preview": text[:100] + "..." if len(text) > 100 else text
            }
            
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to generate audio: {str(e)}"
            }
    
    @staticmethod
    def generate_vocabulary_audio(words: List[Dict[str, str]], language: str = 'english') -> Dict[str, Any]:
        """
        Generate audio for vocabulary words with definitions.
        
        Args:
            words: List of {"word": "...", "definition": "..."}
            language: Target language
        
        Returns:
            Dict with success status and file URL
        """
        if not GTTS_AVAILABLE:
            return {"success": False, "error": "TTS not available"}
        
        try:
            # Build vocabulary text with pauses
            vocab_text = ""
            for item in words:
                word = item.get('word', '')
                definition = item.get('definition', '')
                vocab_text += f"{word}. {definition}. "
            
            lang_code = AudioGenerator.LANGUAGES.get(language.lower(), 'en')
            
            file_id = str(uuid.uuid4())[:8]
            filename = f"vocabulary_{file_id}.mp3"
            filepath = os.path.join(MEDIA_DIR, filename)
            
            tts = gTTS(text=vocab_text, lang=lang_code, slow=True)
            tts.save(filepath)
            
            return {
                "success": True,
                "file_url": f"/static/generated_media/{filename}",
                "filename": filename,
                "word_count": len(words)
            }
            
        except Exception as e:
            logger.error(f"Error generating vocabulary audio: {str(e)}")
            return {"success": False, "error": str(e)}


class ElevenLabsAudioGenerator:
    """
    Generate high-quality audio using ElevenLabs API.
    Free tier: 10,000 characters/month with pre-made voices.
    Falls back to gTTS if ElevenLabs unavailable or quota exceeded.
    """
    
    # Voice recommendations by use case
    VOICE_RECOMMENDATIONS = {
        'lesson': 'rachel',        # Clear, friendly for lessons
        'story': 'matthew',        # Good for storytelling/audiobooks  
        'conversation': 'dave',    # Natural conversational
        'formal': 'paul',          # Professional narration
        'child_friendly': 'emily', # Soft, gentle for young learners
        'energetic': 'josh',       # Enthusiastic, engaging
        'calm': 'thomas',          # Calm, soothing
    }
    
    @staticmethod
    def get_available_voices() -> Dict[str, str]:
        """Return available voices with descriptions"""
        return {
            'rachel': 'Rachel - Clear, friendly American female (recommended)',
            'sarah': 'Sarah - Professional news-style female',
            'emily': 'Emily - Calm, gentle female (great for young learners)',
            'matilda': 'Matilda - Warm, engaging female',
            'adam': 'Adam - Deep, confident American male',
            'josh': 'Josh - Deep, enthusiastic male',
            'thomas': 'Thomas - Calm, soothing American male',
            'matthew': 'Matthew - Natural audiobook male',
            'dave': 'Dave - British conversational male',
            'charlie': 'Charlie - Australian friendly male',
            'paul': 'Paul - Professional narration male',
        }
    
    @staticmethod
    def generate_audio(
        text: str, 
        voice: str = 'rachel',
        subject: str = None,
        content_type: str = 'lesson',
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ) -> Dict[str, Any]:
        """
        Generate audio using ElevenLabs TTS API.
        
        Args:
            text: Text to convert to speech (max ~5000 chars for free tier efficiency)
            voice: Voice name from ELEVENLABS_VOICES
            subject: Optional subject for context (math, english, science, etc.)
            content_type: Type of content (lesson, story, explanation, exercise)
            stability: Voice stability (0-1, higher = more consistent)
            similarity_boost: Voice clarity (0-1, higher = clearer)
        
        Returns:
            Dict with success status and file URL
        """
        if not text or len(text.strip()) < 5:
            return {"success": False, "error": "Text too short for audio generation"}
        
        # Try ElevenLabs first
        if ELEVENLABS_API_KEY and ELEVENLABS_AVAILABLE:
            result = ElevenLabsAudioGenerator._generate_elevenlabs(
                text, voice, stability, similarity_boost
            )
            if result.get("success"):
                return result
            logger.warning(f"ElevenLabs failed, falling back to gTTS: {result.get('error')}")
        
        # Fall back to gTTS
        if GTTS_AVAILABLE:
            return AudioGenerator.generate_reading_audio(text, speed='normal', language='english')
        
        return {"success": False, "error": "No TTS service available. Please configure ElevenLabs API key."}
    
    @staticmethod
    def _generate_elevenlabs(
        text: str,
        voice: str,
        stability: float,
        similarity_boost: float
    ) -> Dict[str, Any]:
        """Internal method to call ElevenLabs API"""
        try:
            # Get voice ID
            voice_id = ELEVENLABS_VOICES.get(voice.lower(), ELEVENLABS_VOICES['rachel'])
            
            # Generate unique filename
            file_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"elevenlabs_{voice}_{timestamp}_{file_id}.mp3"
            filepath = os.path.join(MEDIA_DIR, filename)
            
            # ElevenLabs API call
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": ELEVENLABS_API_KEY
            }
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost
                }
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=60)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                # Estimate duration (~150 words per minute)
                word_count = len(text.split())
                duration_seconds = (word_count / 150) * 60
                
                return {
                    "success": True,
                    "file_url": f"/static/generated_media/{filename}",
                    "filename": filename,
                    "voice": voice,
                    "provider": "elevenlabs",
                    "word_count": word_count,
                    "char_count": len(text),
                    "estimated_duration": f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}",
                    "text_preview": text[:100] + "..." if len(text) > 100 else text
                }
            
            elif response.status_code == 401:
                return {"success": False, "error": "Invalid ElevenLabs API key"}
            elif response.status_code == 429:
                return {"success": False, "error": "ElevenLabs quota exceeded. Using fallback."}
            else:
                return {"success": False, "error": f"ElevenLabs API error: {response.status_code}"}
                
        except requests.Timeout:
            return {"success": False, "error": "ElevenLabs request timed out"}
        except Exception as e:
            logger.error(f"ElevenLabs error: {str(e)}")
            return {"success": False, "error": f"ElevenLabs error: {str(e)}"}
    
    @staticmethod
    def generate_lesson_audio(
        lesson_content: str,
        title: str = "Lesson",
        subject: str = None,
        voice: str = None
    ) -> Dict[str, Any]:
        """
        Generate audio for a complete lesson.
        
        Args:
            lesson_content: Full lesson text
            title: Lesson title
            subject: Subject area (for voice selection)
            voice: Specific voice to use (optional)
        """
        # Auto-select voice based on subject if not specified
        if not voice:
            subject_voices = {
                'english': 'rachel',
                'mathematics': 'thomas',
                'science': 'paul',
                'kiswahili': 'rachel',  # Clear pronunciation
                'social_studies': 'matthew',
                'creative_arts': 'emily',
            }
            voice = subject_voices.get(subject.lower() if subject else '', 'rachel')
        
        # Add title announcement
        full_text = f"{title}. {lesson_content}"
        
        return ElevenLabsAudioGenerator.generate_audio(
            text=full_text,
            voice=voice,
            subject=subject,
            content_type='lesson'
        )
    
    @staticmethod
    def generate_vocabulary_audio(
        words: List[Dict[str, str]],
        voice: str = 'rachel',
        include_definitions: bool = True
    ) -> Dict[str, Any]:
        """
        Generate vocabulary pronunciation audio.
        
        Args:
            words: List of {"word": "...", "definition": "..."}
            voice: Voice to use
            include_definitions: Whether to read definitions too
        """
        if not words:
            return {"success": False, "error": "No words provided"}
        
        # Build vocabulary text with natural pauses
        parts = []
        for item in words:
            word = item.get('word', '')
            if include_definitions:
                definition = item.get('definition', '')
                parts.append(f"{word}. {definition}")
            else:
                parts.append(word)
        
        vocab_text = ". ".join(parts) + "."
        
        return ElevenLabsAudioGenerator.generate_audio(
            text=vocab_text,
            voice=voice,
            content_type='vocabulary'
        )
    
    @staticmethod  
    def generate_story_audio(
        story_text: str,
        title: str = "Story",
        voice: str = 'matthew'
    ) -> Dict[str, Any]:
        """
        Generate narrated story/reading passage audio.
        Best for reading comprehension exercises.
        """
        full_text = f"{title}. {story_text}"
        return ElevenLabsAudioGenerator.generate_audio(
            text=full_text,
            voice=voice,
            content_type='story'
        )
    
    @staticmethod
    def generate_exercise_audio(
        instructions: str,
        questions: List[str] = None,
        voice: str = 'sarah'
    ) -> Dict[str, Any]:
        """
        Generate audio for exercises/assessments.
        Reads instructions and optionally questions.
        """
        full_text = instructions
        if questions:
            full_text += " " + " ".join([f"Question {i+1}. {q}" for i, q in enumerate(questions)])
        
        return ElevenLabsAudioGenerator.generate_audio(
            text=full_text,
            voice=voice,
            content_type='exercise'
        )


class FlashcardGenerator:
    """Generate interactive flashcards for learning"""
    
    @staticmethod
    def generate_flashcards(topic: str, items: List[Dict[str, str]], 
                           card_type: str = 'vocabulary') -> Dict[str, Any]:
        """
        Generate flashcard set as HTML/JSON.
        
        Args:
            topic: The topic/title for the flashcard set
            items: List of {"front": "...", "back": "..."}
            card_type: 'vocabulary', 'concept', 'question'
        
        Returns:
            Dict with flashcard data and HTML file
        """
        if not items:
            return {"success": False, "error": "No flashcard items provided"}
        
        try:
            file_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save flashcard data as JSON
            json_filename = f"flashcards_{timestamp}_{file_id}.json"
            json_filepath = os.path.join(MEDIA_DIR, json_filename)
            
            flashcard_data = {
                "topic": topic,
                "type": card_type,
                "created": datetime.now().isoformat(),
                "card_count": len(items),
                "cards": items
            }
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(flashcard_data, f, ensure_ascii=False, indent=2)
            
            # Generate interactive HTML file
            html_filename = f"flashcards_{timestamp}_{file_id}.html"
            html_filepath = os.path.join(MEDIA_DIR, html_filename)
            
            html_content = FlashcardGenerator._generate_flashcard_html(topic, items, card_type)
            
            with open(html_filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return {
                "success": True,
                "html_url": f"/static/generated_media/{html_filename}",
                "json_url": f"/static/generated_media/{json_filename}",
                "topic": topic,
                "card_count": len(items),
                "cards": items,
                "type": card_type
            }
            
        except Exception as e:
            logger.error(f"Error generating flashcards: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _generate_flashcard_html(topic: str, items: List[Dict[str, str]], card_type: str) -> str:
        """Generate interactive HTML for flashcards"""
        
        cards_json = json.dumps(items)
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flashcards - {topic}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem;
        }}
        h1 {{
            color: white;
            margin-bottom: 1rem;
            text-align: center;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .info {{
            color: rgba(255,255,255,0.9);
            margin-bottom: 2rem;
            font-size: 1.1rem;
        }}
        .flashcard-container {{
            perspective: 1000px;
            width: 100%;
            max-width: 500px;
            height: 300px;
            margin-bottom: 2rem;
        }}
        .flashcard {{
            width: 100%;
            height: 100%;
            position: relative;
            transform-style: preserve-3d;
            transition: transform 0.6s;
            cursor: pointer;
        }}
        .flashcard.flipped {{
            transform: rotateY(180deg);
        }}
        .flashcard-face {{
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            font-size: 1.4rem;
            text-align: center;
        }}
        .flashcard-front {{
            background: white;
            color: #333;
        }}
        .flashcard-back {{
            background: #4CAF50;
            color: white;
            transform: rotateY(180deg);
        }}
        .controls {{
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        button {{
            padding: 0.8rem 2rem;
            font-size: 1rem;
            border: none;
            border-radius: 30px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 600;
        }}
        .btn-prev, .btn-next {{
            background: white;
            color: #667eea;
        }}
        .btn-prev:hover, .btn-next:hover {{
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        .btn-shuffle {{
            background: #FF6B9D;
            color: white;
        }}
        .progress {{
            color: white;
            font-size: 1.2rem;
            margin-bottom: 1rem;
        }}
        .instruction {{
            color: rgba(255,255,255,0.8);
            font-size: 0.9rem;
            margin-top: 1rem;
        }}
        @media print {{
            body {{ background: white; }}
            .controls, .instruction {{ display: none; }}
            .flashcard-container {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <h1>📚 {topic}</h1>
    <p class="info">{len(items)} Flashcards | {card_type.title()}</p>
    
    <div class="progress">
        Card <span id="currentCard">1</span> of <span id="totalCards">{len(items)}</span>
    </div>
    
    <div class="flashcard-container">
        <div class="flashcard" id="flashcard" onclick="flipCard()">
            <div class="flashcard-face flashcard-front" id="front">
                Loading...
            </div>
            <div class="flashcard-face flashcard-back" id="back">
                Loading...
            </div>
        </div>
    </div>
    
    <div class="controls">
        <button class="btn-prev" onclick="prevCard()">← Previous</button>
        <button class="btn-shuffle" onclick="shuffleCards()">🔀 Shuffle</button>
        <button class="btn-next" onclick="nextCard()">Next →</button>
    </div>
    
    <p class="instruction">Click the card to flip it. Use keyboard: ← → to navigate, Space to flip</p>
    
    <script>
        let cards = {cards_json};
        let currentIndex = 0;
        let isFlipped = false;
        
        function showCard(index) {{
            const card = cards[index];
            document.getElementById('front').textContent = card.front;
            document.getElementById('back').textContent = card.back;
            document.getElementById('currentCard').textContent = index + 1;
            
            // Reset flip state
            if (isFlipped) {{
                document.getElementById('flashcard').classList.remove('flipped');
                isFlipped = false;
            }}
        }}
        
        function flipCard() {{
            const flashcard = document.getElementById('flashcard');
            flashcard.classList.toggle('flipped');
            isFlipped = !isFlipped;
        }}
        
        function nextCard() {{
            currentIndex = (currentIndex + 1) % cards.length;
            showCard(currentIndex);
        }}
        
        function prevCard() {{
            currentIndex = (currentIndex - 1 + cards.length) % cards.length;
            showCard(currentIndex);
        }}
        
        function shuffleCards() {{
            for (let i = cards.length - 1; i > 0; i--) {{
                const j = Math.floor(Math.random() * (i + 1));
                [cards[i], cards[j]] = [cards[j], cards[i]];
            }}
            currentIndex = 0;
            showCard(currentIndex);
        }}
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'ArrowRight') nextCard();
            else if (e.key === 'ArrowLeft') prevCard();
            else if (e.key === ' ') {{ e.preventDefault(); flipCard(); }}
        }});
        
        // Initialize
        showCard(0);
    </script>
</body>
</html>'''


class ContentGenerator:
    """Generate various educational content using AI"""
    
    @staticmethod
    def generate_vocabulary_flashcards(subject: str, grade: str, topic: str, count: int = 10) -> Dict[str, Any]:
        """
        Generate vocabulary flashcards for a topic.
        Returns flashcard data that can be rendered interactively.
        """
        # Subject-specific vocabulary templates
        vocabulary_templates = {
            "english": {
                "reading comprehension": [
                    {"front": "Comprehension", "back": "The ability to understand written text"},
                    {"front": "Context Clues", "back": "Hints in the text that help you understand unfamiliar words"},
                    {"front": "Main Idea", "back": "The most important point the author wants to make"},
                    {"front": "Supporting Details", "back": "Facts and information that explain the main idea"},
                    {"front": "Inference", "back": "A conclusion based on evidence and reasoning"},
                    {"front": "Summary", "back": "A brief statement of the main points"},
                    {"front": "Sequence", "back": "The order in which events happen"},
                    {"front": "Compare", "back": "To find similarities between things"},
                    {"front": "Contrast", "back": "To find differences between things"},
                    {"front": "Predict", "back": "To guess what will happen next based on clues"}
                ],
                "grammar": [
                    {"front": "Noun", "back": "A word that names a person, place, thing, or idea"},
                    {"front": "Verb", "back": "A word that shows action or state of being"},
                    {"front": "Adjective", "back": "A word that describes a noun"},
                    {"front": "Adverb", "back": "A word that describes a verb, adjective, or another adverb"},
                    {"front": "Pronoun", "back": "A word that takes the place of a noun"},
                    {"front": "Preposition", "back": "A word that shows relationship between other words"},
                    {"front": "Conjunction", "back": "A word that joins words, phrases, or sentences"},
                    {"front": "Subject", "back": "The person or thing doing the action"},
                    {"front": "Predicate", "back": "The part of a sentence that tells what the subject does"},
                    {"front": "Clause", "back": "A group of words with a subject and verb"}
                ]
            },
            "mathematics": {
                "fractions": [
                    {"front": "Numerator", "back": "The top number in a fraction - shows parts we have"},
                    {"front": "Denominator", "back": "The bottom number in a fraction - shows total parts"},
                    {"front": "Proper Fraction", "back": "A fraction where numerator is less than denominator (e.g., 3/4)"},
                    {"front": "Improper Fraction", "back": "A fraction where numerator is greater than denominator (e.g., 5/3)"},
                    {"front": "Mixed Number", "back": "A whole number and a fraction together (e.g., 2½)"},
                    {"front": "Equivalent Fractions", "back": "Fractions that represent the same value (e.g., 1/2 = 2/4)"},
                    {"front": "Simplify", "back": "To reduce a fraction to its lowest terms"},
                    {"front": "Common Denominator", "back": "When two fractions have the same denominator"},
                    {"front": "LCD", "back": "Least Common Denominator - smallest number both denominators divide into"},
                    {"front": "Reciprocal", "back": "A fraction flipped upside down (e.g., 3/4 becomes 4/3)"}
                ],
                "geometry": [
                    {"front": "Perimeter", "back": "The distance around a shape"},
                    {"front": "Area", "back": "The space inside a 2D shape (measured in square units)"},
                    {"front": "Volume", "back": "The space inside a 3D shape (measured in cubic units)"},
                    {"front": "Angle", "back": "The space between two lines that meet at a point"},
                    {"front": "Right Angle", "back": "An angle that measures exactly 90 degrees"},
                    {"front": "Parallel Lines", "back": "Lines that never meet and stay the same distance apart"},
                    {"front": "Perpendicular", "back": "Lines that meet at a 90-degree angle"},
                    {"front": "Radius", "back": "Distance from the center of a circle to its edge"},
                    {"front": "Diameter", "back": "Distance across a circle through its center (2 × radius)"},
                    {"front": "Circumference", "back": "The distance around a circle"}
                ]
            },
            "science": {
                "plants": [
                    {"front": "Photosynthesis", "back": "The process by which plants make food using sunlight, water, and CO2"},
                    {"front": "Chlorophyll", "back": "The green pigment in leaves that captures sunlight"},
                    {"front": "Transpiration", "back": "The loss of water through leaf pores"},
                    {"front": "Germination", "back": "When a seed starts to grow into a plant"},
                    {"front": "Pollination", "back": "Transfer of pollen from one flower to another"},
                    {"front": "Root", "back": "Plant part that absorbs water and nutrients from soil"},
                    {"front": "Stem", "back": "Plant part that supports leaves and carries water"},
                    {"front": "Leaf", "back": "Plant part where photosynthesis mainly occurs"},
                    {"front": "Stamen", "back": "Male part of a flower that produces pollen"},
                    {"front": "Pistil", "back": "Female part of a flower that contains ovules"}
                ],
                "matter": [
                    {"front": "Matter", "back": "Anything that has mass and takes up space"},
                    {"front": "Solid", "back": "State of matter with fixed shape and volume"},
                    {"front": "Liquid", "back": "State of matter with fixed volume but no fixed shape"},
                    {"front": "Gas", "back": "State of matter with no fixed shape or volume"},
                    {"front": "Evaporation", "back": "When a liquid changes to a gas"},
                    {"front": "Condensation", "back": "When a gas changes to a liquid"},
                    {"front": "Melting", "back": "When a solid changes to a liquid"},
                    {"front": "Freezing", "back": "When a liquid changes to a solid"},
                    {"front": "Atom", "back": "The smallest particle of an element"},
                    {"front": "Molecule", "back": "Two or more atoms bonded together"}
                ]
            },
            "kiswahili": {
                "msamiati": [
                    {"front": "Shule", "back": "School"},
                    {"front": "Mwalimu", "back": "Teacher"},
                    {"front": "Mwanafunzi", "back": "Student"},
                    {"front": "Kitabu", "back": "Book"},
                    {"front": "Kalamu", "back": "Pen"},
                    {"front": "Daftari", "back": "Notebook"},
                    {"front": "Darasa", "back": "Classroom"},
                    {"front": "Somo", "back": "Lesson/Subject"},
                    {"front": "Mtihani", "back": "Examination"},
                    {"front": "Kazi", "back": "Work/Assignment"}
                ]
            }
        }
        
        # Find appropriate vocabulary
        subject_lower = subject.lower()
        topic_lower = topic.lower()
        
        cards = []
        if subject_lower in vocabulary_templates:
            for key, vocab in vocabulary_templates[subject_lower].items():
                if key in topic_lower or topic_lower in key:
                    cards = vocab[:count]
                    break
            if not cards:
                # Get first available topic for subject
                first_topic = list(vocabulary_templates[subject_lower].keys())[0]
                cards = vocabulary_templates[subject_lower][first_topic][:count]
        
        if not cards:
            # Default vocabulary cards
            cards = vocabulary_templates.get("english", {}).get("grammar", [])[:count]
        
        # Generate flashcard file
        result = FlashcardGenerator.generate_flashcards(
            topic=f"{grade} {subject} - {topic}",
            items=cards,
            card_type='vocabulary'
        )
        
        return result
    
    @staticmethod
    def generate_concept_flashcards(concepts: List[str], explanations: List[str], topic: str) -> Dict[str, Any]:
        """Generate flashcards from concept-explanation pairs"""
        if len(concepts) != len(explanations):
            return {"success": False, "error": "Concepts and explanations must match"}
        
        items = [{"front": c, "back": e} for c, e in zip(concepts, explanations)]
        return FlashcardGenerator.generate_flashcards(topic, items, 'concept')
    
    @staticmethod
    def generate_question_flashcards(questions: List[str], answers: List[str], topic: str) -> Dict[str, Any]:
        """Generate Q&A flashcards for revision"""
        if len(questions) != len(answers):
            return {"success": False, "error": "Questions and answers must match"}
        
        items = [{"front": q, "back": a} for q, a in zip(questions, answers)]
        return FlashcardGenerator.generate_flashcards(topic, items, 'question')


def generate_reading_passage_audio(text: str, speeds: List[str] = None) -> Dict[str, Any]:
    """
    Generate audio versions of a reading passage at different speeds.
    Perfect for listening exercises where students compare slow vs. fast reading.
    
    Args:
        text: The passage to convert to audio
        speeds: List of speeds ['slow', 'normal', 'fast']. Defaults to all.
    
    Returns:
        Dict with audio files at different speeds
    """
    if speeds is None:
        speeds = ['slow', 'normal']
    
    results = {
        "success": True,
        "passage_preview": text[:200] + "..." if len(text) > 200 else text,
        "audio_files": []
    }
    
    for speed in speeds:
        audio_result = AudioGenerator.generate_reading_audio(text, speed=speed)
        if audio_result["success"]:
            results["audio_files"].append({
                "speed": speed,
                "url": audio_result["file_url"],
                "duration": audio_result["estimated_duration"]
            })
        else:
            results["audio_files"].append({
                "speed": speed,
                "error": audio_result.get("error", "Failed to generate")
            })
    
    return results


class VideoGenerator:
    """Generate educational videos with ElevenLabs AI narration"""
    
    # Color schemes for videos
    COLOR_SCHEMES = {
        'default': {'bg': (30, 58, 138), 'text': (255, 255, 255), 'accent': (255, 107, 157)},
        'nature': {'bg': (34, 139, 34), 'text': (255, 255, 255), 'accent': (255, 215, 0)},
        'sunset': {'bg': (255, 87, 51), 'text': (255, 255, 255), 'accent': (255, 195, 0)},
        'ocean': {'bg': (0, 119, 182), 'text': (255, 255, 255), 'accent': (144, 224, 239)},
        'purple': {'bg': (103, 58, 183), 'text': (255, 255, 255), 'accent': (255, 193, 7)},
        'dark': {'bg': (26, 26, 26), 'text': (255, 255, 255), 'accent': (255, 107, 157)},
        'warm': {'bg': (139, 69, 19), 'text': (255, 255, 255), 'accent': (255, 215, 0)}
    }
    
    @staticmethod
    def _generate_narration_audio(text: str, voice: str = 'rachel') -> Optional[str]:
        """
        Generate narration audio using ElevenLabs (preferred) or gTTS (fallback).
        Returns the filepath to the generated audio, or None if failed.
        """
        audio_path = os.path.join(MEDIA_DIR, f"narration_{uuid.uuid4().hex[:8]}.mp3")
        
        # Try ElevenLabs first for high-quality voice
        if ELEVENLABS_API_KEY:
            try:
                voice_id = ELEVENLABS_VOICES.get(voice.lower(), ELEVENLABS_VOICES['rachel'])
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": ELEVENLABS_API_KEY
                }
                data = {
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                }
                response = requests.post(url, json=data, headers=headers, timeout=30)
                if response.status_code == 200:
                    with open(audio_path, 'wb') as f:
                        f.write(response.content)
                    return audio_path
                logger.warning(f"ElevenLabs returned {response.status_code}, falling back to gTTS")
            except Exception as e:
                logger.warning(f"ElevenLabs failed: {e}, falling back to gTTS")
        
        # Fallback to gTTS
        if GTTS_AVAILABLE:
            try:
                tts = gTTS(text=text, lang='en', slow=False)
                tts.save(audio_path)
                return audio_path
            except Exception as e:
                logger.error(f"gTTS also failed: {e}")
        
        return None
    
    @staticmethod
    def create_text_frame(text: str, width: int = 1280, height: int = 720, 
                          font_size: int = 60, color_scheme: str = 'default') -> str:
        """Create a single frame image with text"""
        colors = VideoGenerator.COLOR_SCHEMES.get(color_scheme, VideoGenerator.COLOR_SCHEMES['default'])
        
        # Create image with PIL
        img = Image.new('RGB', (width, height), colors['bg'])
        draw = ImageDraw.Draw(img)
        
        # Try to use a nice font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        # Word wrap text
        words = text.split()
        lines = []
        current_line = []
        max_width = width - 100  # padding
        
        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                line_width = bbox[2] - bbox[0]
            except:
                line_width = len(test_line) * font_size * 0.6
            
            if line_width > max_width:
                current_line.pop()
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Calculate total height and starting y
        line_height = font_size + 20
        total_height = len(lines) * line_height
        start_y = (height - total_height) // 2
        
        # Draw text centered
        for i, line in enumerate(lines):
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
            except:
                line_width = len(line) * font_size * 0.6
            
            x = (width - line_width) // 2
            y = start_y + i * line_height
            draw.text((x, y), line, fill=colors['text'], font=font)
        
        # Save frame
        frame_id = str(uuid.uuid4())[:8]
        frame_path = os.path.join(MEDIA_DIR, f"frame_{frame_id}.png")
        img.save(frame_path)
        
        return frame_path
    
    @staticmethod
    def generate_vocabulary_video(words: List[Dict[str, str]], title: str = "Vocabulary",
                                  duration_per_word: float = 4.0, 
                                  with_audio: bool = True,
                                  color_scheme: str = 'default',
                                  voice: str = 'rachel') -> Dict[str, Any]:
        """
        Generate a vocabulary video showing words with definitions.
        Each word appears on screen with ElevenLabs AI pronunciation.
        
        Args:
            words: List of {"word": "...", "definition": "..."}
            title: Video title
            duration_per_word: Seconds to show each word
            with_audio: Whether to include pronunciation audio
            color_scheme: Color theme for the video
            voice: ElevenLabs voice to use (rachel, adam, matthew, etc.)
        """
        if not MOVIEPY_AVAILABLE:
            return {"success": False, "error": "MoviePy not installed. Cannot generate videos."}
        
        if not words:
            return {"success": False, "error": "No words provided"}
        
        try:
            clips = []
            temp_files = []
            
            # Title slide
            title_frame = VideoGenerator.create_text_frame(
                title, 
                font_size=80,
                color_scheme=color_scheme
            )
            temp_files.append(title_frame)
            title_clip = ImageClip(title_frame, duration=3)
            clips.append(title_clip)
            
            # Word slides
            for item in words:
                word = item.get('word', '')
                definition = item.get('definition', '')
                
                # Create frame with word and definition
                text = f"{word}\n\n{definition}"
                frame_path = VideoGenerator.create_text_frame(
                    text,
                    font_size=50,
                    color_scheme=color_scheme
                )
                temp_files.append(frame_path)
                
                clip = ImageClip(frame_path, duration=duration_per_word)
                
                # Add ElevenLabs narration if requested
                if with_audio:
                    audio_text = f"{word}. {definition}"
                    audio_path = VideoGenerator._generate_narration_audio(audio_text, voice)
                    
                    if audio_path:
                        temp_files.append(audio_path)
                        try:
                            audio_clip = AudioFileClip(audio_path)
                            # Extend video duration to match audio if needed
                            if audio_clip.duration > duration_per_word:
                                clip = ImageClip(frame_path, duration=audio_clip.duration + 0.5)
                            clip = clip.with_audio(audio_clip)
                        except Exception as e:
                            logger.warning(f"Could not add audio: {e}")
                
                clips.append(clip)
            
            # End slide
            end_frame = VideoGenerator.create_text_frame(
                "Keep Learning!", 
                font_size=70,
                color_scheme=color_scheme
            )
            temp_files.append(end_frame)
            end_clip = ImageClip(end_frame, duration=2)
            clips.append(end_clip)
            
            # Concatenate all clips
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Save video
            file_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vocabulary_video_{timestamp}_{file_id}.mp4"
            filepath = os.path.join(MEDIA_DIR, filename)
            
            final_video.write_videofile(
                filepath,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(MEDIA_DIR, 'temp_audio.m4a'),
                remove_temp=True,
                logger=None  # Suppress verbose output
            )
            
            # Cleanup temp files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            
            # Calculate duration
            total_duration = final_video.duration
            
            return {
                "success": True,
                "file_url": f"/static/generated_media/{filename}",
                "filename": filename,
                "title": title,
                "word_count": len(words),
                "duration": f"{int(total_duration // 60)}:{int(total_duration % 60):02d}",
                "with_audio": with_audio
            }
            
        except Exception as e:
            logger.error(f"Error generating vocabulary video: {str(e)}")
            return {"success": False, "error": f"Failed to generate video: {str(e)}"}
    
    @staticmethod
    def generate_slideshow_video(slides: List[Dict[str, str]], title: str = "Lesson",
                                 duration_per_slide: float = 5.0,
                                 with_audio: bool = True,
                                 color_scheme: str = 'default',
                                 voice: str = 'rachel') -> Dict[str, Any]:
        """
        Generate a slideshow video with multiple text slides and ElevenLabs AI narration.
        
        Args:
            slides: List of {"title": "...", "content": "..."}
            title: Video title
            duration_per_slide: Base seconds per slide (extended if audio is longer)
            with_audio: Whether to add text-to-speech narration
            color_scheme: Color theme
            voice: ElevenLabs voice to use for narration
        """
        if not MOVIEPY_AVAILABLE:
            return {"success": False, "error": "MoviePy not installed. Cannot generate videos."}
        
        if not slides:
            return {"success": False, "error": "No slides provided"}
        
        try:
            clips = []
            temp_files = []
            
            # Title slide
            title_frame = VideoGenerator.create_text_frame(
                title,
                font_size=80,
                color_scheme=color_scheme
            )
            temp_files.append(title_frame)
            title_clip = ImageClip(title_frame, duration=3)
            clips.append(title_clip)
            
            # Content slides
            for i, slide in enumerate(slides):
                slide_title = slide.get('title', f'Slide {i+1}')
                content = slide.get('content', '')
                
                # Create frame
                text = f"{slide_title}\n\n{content}"
                frame_path = VideoGenerator.create_text_frame(
                    text,
                    font_size=45,
                    color_scheme=color_scheme
                )
                temp_files.append(frame_path)
                
                clip = ImageClip(frame_path, duration=duration_per_slide)
                
                # Add ElevenLabs AI narration
                if with_audio and content:
                    narration = f"{slide_title}. {content}"
                    audio_path = VideoGenerator._generate_narration_audio(narration, voice)
                    
                    if audio_path:
                        temp_files.append(audio_path)
                        try:
                            audio_clip = AudioFileClip(audio_path)
                            if audio_clip.duration > duration_per_slide:
                                clip = ImageClip(frame_path, duration=audio_clip.duration + 1)
                            clip = clip.with_audio(audio_clip)
                        except Exception as e:
                            logger.warning(f"Could not add narration: {e}")
                
                clips.append(clip)
            
            # End slide
            end_frame = VideoGenerator.create_text_frame(
                "Thank You for Learning!",
                font_size=60,
                color_scheme=color_scheme
            )
            temp_files.append(end_frame)
            end_clip = ImageClip(end_frame, duration=2)
            clips.append(end_clip)
            
            # Concatenate
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Save
            file_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"slideshow_{timestamp}_{file_id}.mp4"
            filepath = os.path.join(MEDIA_DIR, filename)
            
            final_video.write_videofile(
                filepath,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(MEDIA_DIR, 'temp_audio.m4a'),
                remove_temp=True,
                logger=None
            )
            
            # Cleanup
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            
            return {
                "success": True,
                "file_url": f"/static/generated_media/{filename}",
                "filename": filename,
                "title": title,
                "slide_count": len(slides),
                "duration": f"{int(final_video.duration // 60)}:{int(final_video.duration % 60):02d}",
                "with_audio": with_audio
            }
            
        except Exception as e:
            logger.error(f"Error generating slideshow: {str(e)}")
            return {"success": False, "error": f"Failed to generate video: {str(e)}"}
    
    @staticmethod
    def generate_reading_video(text: str, title: str = "Reading Practice",
                               speed: str = 'normal',
                               color_scheme: str = 'ocean',
                               voice: str = 'rachel') -> Dict[str, Any]:
        """
        Generate a video of text being read aloud with ElevenLabs AI voices.
        Great for reading along exercises - text appears sentence by sentence 
        with synchronized professional narration.
        
        Args:
            text: The passage to read
            title: Video title
            speed: 'slow' or 'normal' reading speed
            color_scheme: Color theme
            voice: ElevenLabs voice to use for narration
        """
        if not MOVIEPY_AVAILABLE:
            return {"success": False, "error": "MoviePy not installed. Cannot generate videos."}
        
        if not text:
            return {"success": False, "error": "No text provided"}
        
        try:
            # Split into sentences
            import re
            sentences = re.split(r'(?<=[.!?])\s+', text.strip())
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                return {"success": False, "error": "Could not parse text into sentences"}
            
            clips = []
            temp_files = []
            
            # Title slide
            title_frame = VideoGenerator.create_text_frame(
                title,
                font_size=70,
                color_scheme=color_scheme
            )
            temp_files.append(title_frame)
            title_clip = ImageClip(title_frame, duration=3)
            clips.append(title_clip)
            
            # Sentence slides with ElevenLabs AI audio
            for sentence in sentences:
                # Create frame
                frame_path = VideoGenerator.create_text_frame(
                    sentence,
                    font_size=50,
                    color_scheme=color_scheme
                )
                temp_files.append(frame_path)
                
                # Generate audio for sentence using ElevenLabs
                audio_path = VideoGenerator._generate_narration_audio(sentence, voice)
                
                if audio_path:
                    temp_files.append(audio_path)
                    try:
                        audio_clip = AudioFileClip(audio_path)
                        # Add extra pause for slow mode
                        pause = 2 if speed == 'slow' else 1
                        duration = audio_clip.duration + pause
                        clip = ImageClip(frame_path, duration=duration)
                        clip = clip.with_audio(audio_clip)
                        clips.append(clip)
                    except Exception as e:
                        # Fallback without audio
                        logger.warning(f"Could not add audio: {e}")
                        clip = ImageClip(frame_path, duration=5)
                        clips.append(clip)
                else:
                    clip = ImageClip(frame_path, duration=5)
                    clips.append(clip)
            
            # End slide
            end_frame = VideoGenerator.create_text_frame(
                "Great Reading!",
                font_size=70,
                color_scheme=color_scheme
            )
            temp_files.append(end_frame)
            end_clip = ImageClip(end_frame, duration=2)
            clips.append(end_clip)
            
            # Concatenate
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Save
            file_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reading_{speed}_{timestamp}_{file_id}.mp4"
            filepath = os.path.join(MEDIA_DIR, filename)
            
            final_video.write_videofile(
                filepath,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(MEDIA_DIR, 'temp_audio.m4a'),
                remove_temp=True,
                logger=None
            )
            
            # Cleanup
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            
            return {
                "success": True,
                "file_url": f"/static/generated_media/{filename}",
                "filename": filename,
                "title": title,
                "sentence_count": len(sentences),
                "speed": speed,
                "duration": f"{int(final_video.duration // 60)}:{int(final_video.duration % 60):02d}"
            }
            
        except Exception as e:
            logger.error(f"Error generating reading video: {str(e)}")
            return {"success": False, "error": f"Failed to generate video: {str(e)}"}


def cleanup_old_media(days_old: int = 7):
    """Remove generated media files older than specified days"""
    import time
    
    cutoff = time.time() - (days_old * 86400)
    removed = 0
    
    for filename in os.listdir(MEDIA_DIR):
        filepath = os.path.join(MEDIA_DIR, filename)
        if os.path.isfile(filepath):
            if os.path.getmtime(filepath) < cutoff:
                try:
                    os.remove(filepath)
                    removed += 1
                except Exception as e:
                    logger.error(f"Failed to remove {filename}: {e}")
    
    return {"removed": removed}

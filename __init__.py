import json
import os
from ovos_workshop.skills.ovos import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_utils.log import LOG

DEFAULT_SETTINGS = {
    "intro_played": False  # Track whether the intro has been played
}

class RiddleSkill(OVOSSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.override = True

    def initialize(self):
        """Initialize the skill and load settings."""
        self.settings.merge(DEFAULT_SETTINGS, new_only=True)
        self.settings_change_callback = self.on_settings_changed
        self.current_story = None
        self.stories = self.load_stories()
        self.responses = {"yes": "yes_dialog", "no": "no_dialog", "irrelevant": "irrelevant_dialog"}

    def on_settings_changed(self):
        """Called when settings are changed."""
        self.log.info("Settings have been changed!")

    def load_stories(self):
        """Load stories from an external JSON file based on language."""
        lang = self.lang.lower()  # Ensure the language code is in lowercase
        
        # Construct the path to the locale directory and language-specific JSON file
        stories_file = os.path.join(os.path.dirname(__file__), "locale", lang, f"stories_{lang}.json")
        
        # Log the file path to check what it is looking for
        LOG.debug(f"Loading stories from: {stories_file}")
        
        try:
            with open(stories_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.log.error(f"The file '{stories_file}' could not be found.")
            return []
        except json.JSONDecodeError:
            self.log.error(f"The file '{stories_file}' contains invalid JSON.")
            return []

    def play_intro(self):
        """Play the introduction only if it hasn't been played yet."""
        if not self.settings.get("intro_played", False):
            # Use the dialog file for the introduction
            self.speak_dialog("intro", wait=True)  # The 'intro' dialog file will be used
            # Mark the intro as played in the settings
            self.settings["intro_played"] = True
            self.settings.store()  # Save settings

    @intent_handler("StartGame.intent")
    def start_game(self, message):
        # Play the intro only the first time
        self.play_intro()
    
        if not self.stories:
            self.speak_dialog("no_stories")
            return
    
        self.current_story = self.stories[0]  # Select the first story in the list
        self.speak_dialog("riddle_prompt", {"story": self.current_story['story']}, wait=True)
    
        # Start a loop where the user can continue asking questions
        while self.current_story:
            # Ensure that the "ask_question_prompt" dialog finishes before waiting for input
            self.speak_dialog("ask_question_prompt", wait=True)
    
            user_question = self.get_response(
                num_retries=3,  # Allow 3 attempts
                on_fail="I didn't hear you. The riddle ends now. You can start again by saying 'start a riddle.'"  # Fallback message
            )
    
            if user_question:  # Check if a question is asked
                self.answer_question(user_question)  # Process the question
            else:
                # If no response after 3 attempts, end the riddle
                self.current_story = None

    def answer_question(self, user_question):
        """Verwerk een vraag van de gebruiker."""
        if not self.current_story:
            self.speak("Er is geen lopend raadsel. Zeg 'start een raadsel' om te beginnen.")
            return

        user_question = user_question.lower()  # process the user input

        # Haal de solution_keywords uit de huidige story
        solution_keywords = self.current_story.get("solution_keywords", [])

        if any(keyword in user_question for keyword in solution_keywords):
            self.speak_dialog("congratulations", {"solution": self.current_story['solution']})
            self.current_story = None
            return

        # Yes/No/Irrelevant logic
        yes_keywords = self.current_story["yes_keywords"]
        no_keywords = self.current_story["no_keywords"]

        if any(keyword in user_question for keyword in no_keywords):
            self.speak_dialog(self.responses["no"])  # Use the "no" dialog
        elif any(keyword in user_question for keyword in yes_keywords):
            self.speak_dialog(self.responses["yes"])  # Use the "yes" dialog
        else:
            self.speak_dialog(self.responses["irrelevant"])  # Use the "irrelevant" dialog

    @intent_handler("GiveUp.intent")
    def give_up(self, message):
        if not self.current_story:
            self.speak_dialog("no_ongoing_riddle")
            return
        self.current_story = None

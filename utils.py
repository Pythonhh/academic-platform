
# List of prohibited words (Turkish and English)
# This is a basic list. In a real app, this would be much more extensive or use an external library.
BAD_WORDS = [
    # Turkish
    "amk", "aq", "oc", "oç", "sik", "yarak", "yarrak", "orospu", "piç", "göt", "meme", 
    "kaşar", "kahpe", "sürtük", "ibne", "puşt", "siktir", "sikiş", "amcık", "ananı", 
    "bacını", "şerefsiz", "haysiyetsiz", "dangalak", "gerizekalı", "salak", "aptal",
    
    # English
    "fuck", "shit", "bitch", "asshole", "cunt", "dick", "pussy", "bastard", "nigger", 
    "whore", "slut", "faggot", "cock", "suck", "motherfucker", "idiot", "stupid", "retard"
]

def contains_profanity(text):
    """
    Checks if the given text contains any prohibited words.
    Returns True if profanity is found, False otherwise.
    """
    if not text:
        return False
        
    text_lower = text.lower()
    
    # Check for exact words or words embedded (careful with embedded for short words)
    # For now, let's do simple inclusion check but slightly smarter
    
    for word in BAD_WORDS:
        # Check if the bad word is in the text
        if word in text_lower:
            return True
            
    return False

def clean_text(text):
    """
    Optional: Returns a cleaned version of the text (e.g. with asterisks).
    """
    if not text:
        return text
        
    cleaned = text
    for word in BAD_WORDS:
        if word in cleaned.lower():
            # Replace with asterisks of same length
            cleaned = cleaned.replace(word, '*' * len(word))
            
    return cleaned
